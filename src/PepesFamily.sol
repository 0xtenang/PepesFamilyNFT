// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {ERC2981} from "@openzeppelin/contracts/token/common/ERC2981.sol";
import {Ownable, Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";
import {Address} from "@openzeppelin/contracts/utils/Address.sol";
import {ImdPepeArt} from "./ImdPepeArt.sol";
import {FastBase64} from "./lib/FastBase64.sol";

/// @notice The creator token standard (ERC721-C) that marketplaces read to find a collection's transfer rules.
interface ICreatorToken {
    event TransferValidatorUpdated(address oldValidator, address newValidator);

    function getTransferValidator() external view returns (address validator);
    function getTransferValidationFunction() external view returns (bytes4 functionSignature, bool isViewFunction);
    function setTransferValidator(address validator) external;
}

/// @notice Checks every transfer; reverts the ones the collection doesn't allow.
interface ITransferValidator721 {
    function validateTransfer(address caller, address from, address to, uint256 tokenId) external view;
}

/// @notice Arbitrum's system contract, at 0x64 on every Arbitrum chain (Robinhood Chain included): the chain's own (L2)
///         block numbers and hashes, which `block.number` and `blockhash` don't give there (they follow the parent
///         chain).
interface IArbSys {
    function arbBlockNumber() external view returns (uint256);
    /// @dev Reverts for a block that isn't one of the last 256 before the current one.
    function arbBlockHash(uint256 arbBlockNum) external view returns (bytes32);
}

/// @title PepesFamily: the PEPES FAMILY collection
/// @notice PEPES FAMILY (symbol PEPES): 3,333 Pepes drawn from IMD's own Pepe (imd.fun), stored and drawn entirely
///         on chain: ImdPepeArt writes each NFT's picture (IMD's art in one of 19 poses, recoloured, with a background
///         and maybe an extra) from one of the 3,333 trait sets in ImdPepeSpecs (no two alike; four of them 1/1s). Minted blind,
///         then revealed: a keyed shuffle of the token ids, from a seed nobody can know before everyone can, decides
///         which token gets which trait set.
///
///         Built on I'M DEGEN (MineWorldCrafters, github.com/AdamNakamoto/MineWorld): the same mint, reveal, royalty
///         enforcement and links, with the game's parts (the attributes extension) left out.
///
///         The 5% royalty is enforced. Every transfer is checked by a transfer validator (OpenSea's creator fee
///         enforcement registry at launch), so marketplaces can only move PEPES in sales that pay it. Holders can
///         always move their own PEPES between wallets. The validator can be replaced (if marketplaces move to a new
///         one) but never set to nothing, and the 5% rate is fixed. Enforcement is only as strict as that validator,
///         though, and the owner chooses it: see `setTransferValidator`.
/// @dev Trust: the owner sets the price (0 allowed), the per-wallet mint limit, the treasury (mint money and the
///      royalty), the collection's description, website and X links, its picture and banner and its page
///      (contractURI), and the transfer validator, which decides which transfers between wallets go through: it can't
///      move anyone's PEPES, but a bad one could hold transfers up (mints never touch it), and a lax one relaxes the
///      royalty's enforcement. The links, pictures and description can be changed at any time, sold out or not. The
///      art, the trait sets and the 5% royalty rate can't be changed. The owner publishes the committed secret before
///      the block whose hash completes the seed exists, and anyone then seals it, so the owner can't pick looks nor
///      know them before everyone else (see `reveal` and `seal`). Its one lever: if a whole window passes with nobody
///      sealing, it alone can re-roll, at most three times, each in public (`moveEntropyOn`). The mint is for wallets
///      only (`mint`), within a per-address limit. Ownership moves in two steps and can't be renounced, so the links
///      can always be updated. Holders' PEPES and ETH are never within the owner's reach.
contract PepesFamily is ERC721, ERC2981, Ownable2Step, ICreatorToken {
    using Strings for uint256;

    uint256 public constant MAX_SUPPLY = 3333;
    uint256 public constant MAX_PER_TX = 5;
    /// @notice The highest per-wallet limit the owner can set.
    uint256 public constant MAX_WALLET_LIMIT = 50;
    uint96 public constant ROYALTY_BPS = 500;
    /// @notice The longest website, X or picture link (bytes).
    uint256 public constant MAX_LINK = 256;
    /// @notice The longest description (bytes).
    uint256 public constant MAX_DESCRIPTION = 1000;
    /// @notice ArbSys, Arbitrum's system contract. Where it has no code (a local chain), plain `block.number` and
    ///         `blockhash` stand in for its block numbers and hashes.
    address public constant ARB_SYS = address(100);
    /// @notice How many blocks back the chain gives a block's hash (ArbSys and `blockhash` alike): the time anyone has
    ///         to `seal` once the entropy block is over.
    uint256 public constant ENTROPY_WINDOW = 256;
    /// @notice How many times, in all, the owner can move the entropy block on after a window nobody sealed in.
    uint256 public constant MAX_ENTROPY_MOVES = 3;
    /// @notice How many of the window's last blocks `revealStatus` already reads as `Expired`, though `seal` still
    ///         works in them: about 3 seconds of Robinhood Chain's ~0.1 s blocks.
    uint256 public constant SEAL_MARGIN = 30;

    /// @dev validateTransfer(address,address,address,uint256)
    bytes4 private constant VALIDATE_TRANSFER = 0xcaee23ea;

    /// @notice Where the reveal stands: `None` (the secret isn't public yet), `Waiting` (it is; the entropy block
    ///         isn't over), `Sealable` (anyone can `seal` now), `Expired` (the window is over or about to be: then only
    ///         the owner can move the entropy block on, `moveEntropyOn`), `Revealed` (the seed is set), `Stuck`
    ///         (expired with no move left: the PEPES stay sealed for good).
    enum RevealStatus {
        None,
        Waiting,
        Sealable,
        Expired,
        Revealed,
        Stuck
    }

    /// @notice Draws every Pepe (fixed for good).
    ImdPepeArt public immutable art;
    bytes32 public immutable seedCommit;

    /// @notice Per Pepe, in wei (0: free).
    uint256 public price;
    /// @notice How many Pepes one wallet can mint in all (the owner can change it, 1 to MAX_WALLET_LIMIT).
    uint256 public walletLimit = 3;
    bool public saleOpen;
    /// @notice The secret committed at deploy (`seedCommit`), public from `reveal` on.
    uint256 public revealedSecret;
    /// @notice The chain block whose hash `seal` mixes with the secret. 0 until `reveal`.
    uint256 public entropyBlock;
    /// @notice How many times the owner has moved the entropy block on (at most MAX_ENTROPY_MOVES).
    uint256 public entropyMoves;
    uint256 public totalMinted;
    /// @notice How many Pepes each wallet has minted (transfers don't change it).
    mapping(address => uint256) public mintedBy;
    address public treasury;

    uint256 public seed; // 0 until revealed

    address public transferValidator;
    /// @notice The project's website, shown as the collection's link on marketplaces ("" until set).
    string public website;
    /// @notice The project's X (Twitter) link, shown in the collection's description ("" until set).
    string public xLink;
    /// @notice The collection's picture and banner on marketplaces (URLs: OpenSea doesn't take data: URIs for these).
    string public collectionImage;
    string public bannerImage;
    /// @notice The collection's description (and every Pepe's), changeable by the owner.
    string public description =
        "3,333 Pepes on Robinhood Chain, drawn from IMD's own Pepe. Every picture is stored and drawn entirely on chain, and no two look alike.";
    /// @dev Replaces the built-in collection metadata when set (see contractURI).
    string private customContractURI;

    /// @notice The seed is set (by `seal`): every Pepe's look is fixed and public.
    event Revealed(uint256 seed);
    event SaleOpen(bool open);
    /// @notice The owner published the secret; the hash of chain block `entropyBlock` (not yet made) completes the seed.
    event SecretRevealed(uint256 secret, uint256 entropyBlock);
    /// @notice Nobody sealed in time, so the owner moved the seed on to chain block `entropyBlock`.
    event EntropyBlockMoved(uint256 entropyBlock, uint256 moves);
    event PriceSet(uint256 price);
    event WalletLimitSet(uint256 limit);
    event TreasurySet(address indexed treasury);
    event LinksSet(string website, string xLink);
    event CollectionImagesSet(string image, string banner);
    event DescriptionSet(string description);
    /// @notice ERC-7572: marketplaces re-read contractURI when they see this.
    event ContractURIUpdated();
    /// @notice ERC-4906: marketplaces re-read this token's metadata.
    event MetadataUpdate(uint256 _tokenId);
    /// @notice ERC-4906: marketplaces re-read these tokens' metadata.
    event BatchMetadataUpdate(uint256 _fromTokenId, uint256 _toTokenId);

    error SaleClosed();
    error BadQuantity();
    error SoldOut();
    /// @notice This wallet would go over the per-wallet limit.
    error WalletLimit();
    /// @notice Only a wallet minting for itself can mint (msg.sender == tx.origin): not a contract.
    error OnlyWallets();
    error BadWalletLimit();
    error WrongPayment();
    error NotRevealed();
    error AlreadyRevealed();
    error SaleStillOpen();
    /// @notice The entropy block isn't over yet: seal from the next block on.
    error RevealTooSoon();
    /// @notice The owner hasn't published the secret yet (`reveal`), so there's nothing to seal.
    error NoSecret();
    /// @notice Nobody sealed within the window: only the owner can move it on (`moveEntropyOn`).
    error EntropyExpired();
    /// @notice The entropy block's window isn't over: seal instead (anyone can).
    error NotExpired();
    /// @notice The owner has moved the entropy block on MAX_ENTROPY_MOVES times already.
    error NoMovesLeft();
    /// @notice The chain didn't give the entropy block's hash (never expected within the window: nothing is changed).
    error EntropyUnavailable();
    error BadSecret();
    error ZeroAddress();
    error NotAContract();
    /// @notice The treasury can't be this contract (it refuses ETH, so no paid mint could go through).
    error BadTreasury();
    /// @notice The treasury refused a plain call with no ETH, so it would refuse mint money too.
    error TreasuryRefusesEth();
    /// @notice A link or description is too long, or has a character that would break the JSON (", \ or a control).
    error BadLink();
    /// @notice Ownership can only be handed over (two-step), never renounced: the links must stay updatable.
    error CannotRenounce();

    constructor(
        address owner_,
        address treasury_,
        uint256 price_,
        bytes32 seedCommit_,
        address validator_,
        ImdPepeArt art_
    ) ERC721("PEPES FAMILY", "PEPES") Ownable(owner_) {
        _checkTreasury(treasury_);
        if (address(art_).code.length == 0) revert NotAContract();
        treasury = treasury_;
        price = price_;
        seedCommit = seedCommit_;
        art = art_;
        _setDefaultRoyalty(treasury_, ROYALTY_BPS);
        _setValidator(validator_);
    }

    // ---------------------------------------------------------------- mint

    /// @notice Mint `quantity` sealed Pepes (1 to MAX_PER_TX), paying exactly `price` each (nothing while free).
    ///         Wallets only: the caller must be the transaction's sender (msg.sender == tx.origin, else `OnlyWallets`),
    ///         so no contract mints, and one transaction can't sweep the mint through throwaway contracts. An account
    ///         delegated with EIP-7702 still mints as itself, within the same limit per address. Smart-contract wallets
    ///         (a Safe, say) can't mint; they can buy.
    function mint(uint256 quantity) external payable {
        if (msg.sender != tx.origin) revert OnlyWallets();
        if (!saleOpen) revert SaleClosed();
        if (quantity == 0 || quantity > MAX_PER_TX) revert BadQuantity();
        uint256 minted = totalMinted;
        if (minted + quantity > MAX_SUPPLY) revert SoldOut();
        uint256 mine = mintedBy[msg.sender] + quantity;
        if (mine > walletLimit) revert WalletLimit();
        if (msg.value != price * quantity) revert WrongPayment();
        mintedBy[msg.sender] = mine;
        totalMinted = minted + quantity;
        for (uint256 i = 1; i <= quantity; ++i) {
            _mint(msg.sender, minted + i);
        }
        // Paid straight to the treasury, with anything ever forced in here: this contract never holds ETH.
        uint256 balance = address(this).balance;
        if (balance != 0) Address.sendValue(payable(treasury), balance);
    }

    // ---------------------------------------------------------------- reveal

    /// @notice Publish the committed secret, and end the sale for good. The sale must be closed and the secret must
    ///         match `seedCommit`. It becomes public (`revealedSecret`), and the seed waits for the hash of the chain's
    ///         next block (`entropyBlock`): `seal`, which anyone can call once that block is over, sets
    ///         seed = keccak256(abi.encode(secret, that block's hash)). So nobody can know a look before everyone can.
    ///         On Robinhood Chain (an Arbitrum Orbit chain) the blocks are the chain's own L2 blocks, read from ArbSys.
    function reveal(uint256 secret) external onlyOwner {
        if (entropyBlock != 0) revert AlreadyRevealed();
        if (saleOpen) revert SaleStillOpen();
        if (keccak256(abi.encode(secret)) != seedCommit) revert BadSecret();
        revealedSecret = secret;
        uint256 b = _chainBlock() + 1;
        entropyBlock = b;
        emit SecretRevealed(secret, b);
    }

    /// @notice Set the seed, once the entropy block is over: seed = keccak256(abi.encode(revealedSecret, its hash)),
    ///         never 0. Anyone can call it, and should, at once: the chain gives a block's hash for ENTROPY_WINDOW
    ///         (256) blocks only, about 26 seconds on Robinhood Chain. Later it reverts `EntropyExpired`: only the owner
    ///         can move the entropy block on (`moveEntropyOn`).
    /// @return The seed.
    function seal() external returns (uint256) {
        if (seed != 0) revert AlreadyRevealed();
        uint256 b = entropyBlock;
        if (b == 0) revert NoSecret();
        uint256 current = _chainBlock();
        if (current <= b) revert RevealTooSoon();
        if (current - b > ENTROPY_WINDOW) revert EntropyExpired();
        uint256 s = uint256(keccak256(abi.encode(revealedSecret, _chainBlockHash(b))));
        seed = s == 0 ? 1 : s;
        emit Revealed(seed);
        if (totalMinted != 0) emit BatchMetadataUpdate(1, totalMinted);
        return seed;
    }

    /// @notice After a window nobody sealed in, move the seed on to the chain's next block (then seal it at once).
    ///         The owner only, and at most MAX_ENTROPY_MOVES (3) times in all, each in public (`EntropyBlockMoved`).
    /// @return next The new entropy block.
    function moveEntropyOn() external onlyOwner returns (uint256 next) {
        if (seed != 0) revert AlreadyRevealed();
        uint256 b = entropyBlock;
        if (b == 0) revert NoSecret();
        uint256 current = _chainBlock();
        if (current <= b || current - b <= ENTROPY_WINDOW) revert NotExpired();
        uint256 moves = entropyMoves + 1;
        if (moves > MAX_ENTROPY_MOVES) revert NoMovesLeft();
        entropyMoves = moves;
        next = current + 1;
        entropyBlock = next;
        emit EntropyBlockMoved(next, moves);
    }

    /// @notice Where the reveal stands (see `RevealStatus`): what a sealer checks before sealing.
    function revealStatus() public view returns (RevealStatus) {
        if (seed != 0) return RevealStatus.Revealed;
        uint256 b = entropyBlock;
        if (b == 0) return RevealStatus.None;
        uint256 current = _chainBlock();
        if (current <= b) return RevealStatus.Waiting;
        if (current - b < ENTROPY_WINDOW - SEAL_MARGIN) return RevealStatus.Sealable;
        if (entropyMoves >= MAX_ENTROPY_MOVES && current - b > ENTROPY_WINDOW) return RevealStatus.Stuck;
        return RevealStatus.Expired;
    }

    /// @notice The chain block the reveal counts in: ArbSys's L2 block number, or `block.number` without ArbSys.
    function chainBlock() external view returns (uint256) {
        return _chainBlock();
    }

    function _chainBlock() private view returns (uint256) {
        return ARB_SYS.code.length == 0 ? block.number : IArbSys(ARB_SYS).arbBlockNumber();
    }

    /// @dev Chain block `b`'s hash, `b` within the window (checked by the caller); reverts rather than return 0.
    function _chainBlockHash(uint256 b) private view returns (bytes32 h) {
        h = ARB_SYS.code.length == 0 ? blockhash(b) : IArbSys(ARB_SYS).arbBlockHash(b);
        if (h == 0) revert EntropyUnavailable();
    }

    /// @notice Which of the 3,333 trait sets (ImdPepeArt / ImdPepeSpecs index) token `tokenId` has, once
    ///         revealed. Every token has a different one.
    function traitSetOf(uint256 tokenId) public view returns (uint256) {
        if (seed == 0) revert NotRevealed();
        _requireOwned(tokenId);
        return _shuffle(seed, tokenId - 1);
    }

    /// @dev A keyed shuffle of 0..MAX_SUPPLY-1: a 4-round Feistel network on 12 bits (a permutation of 0..4095),
    ///      repeated until it lands inside the supply. Different inputs always give different outputs.
    function _shuffle(uint256 s, uint256 x) internal pure returns (uint256) {
        do {
            uint256 l = x >> 6;
            uint256 r = x & 63;
            for (uint256 i = 0; i < 4; i++) {
                uint256 f;
                assembly ("memory-safe") {
                    let m := mload(0x40) // scratch past the free memory pointer, never allocated
                    mstore(m, s)
                    mstore(add(m, 0x20), i)
                    mstore(add(m, 0x40), r)
                    f := and(keccak256(m, 0x60), 63)
                }
                (l, r) = (r, l ^ f);
            }
            x = (l << 6) | r;
        } while (x >= MAX_SUPPLY);
        return x;
    }

    // ---------------------------------------------------------------- metadata

    /// @notice Metadata and picture, all on chain: the picture ImdPepeArt draws (an SVG), and its
    ///         traits as attributes.
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        bytes memory json;
        if (seed == 0) {
            json = abi.encodePacked(
                '{"name":"PEPES FAMILY #',
                tokenId.toString(),
                '","description":"A sealed PEPE. Its look is revealed after the mint.","image":"data:image/svg+xml;base64,',
                FastBase64.encode(bytes(art.sealedSvg())),
                '","attributes":[{"trait_type":"Status","value":"Sealed"}]}'
            );
        } else {
            uint256 i = _shuffle(seed, tokenId - 1);
            json = abi.encodePacked(
                '{"name":"PEPES FAMILY #',
                tokenId.toString(),
                '","description":"',
                description,
                _externalUrl(),
                '","image":"data:image/svg+xml;base64,',
                FastBase64.encode(bytes(art.render(i))),
                '","attributes":',
                art.attributes(i),
                "}"
            );
        }
        return string.concat("data:application/json;base64,", FastBase64.encode(json));
    }

    /// @dev `","external_url":"<website>` when the website is set (it closes the field before it).
    function _externalUrl() private view returns (string memory) {
        if (bytes(website).length == 0) return "";
        return string.concat('","external_url":"', website);
    }

    /// @notice The collection's page on marketplaces (ERC-7572): its name and description, and its picture, banner,
    ///         website and X link once the owner has set them (`setCollectionImages`, `setLinks`).
    function contractURI() external view returns (string memory) {
        if (bytes(customContractURI).length != 0) return customContractURI;
        string memory links;
        if (bytes(website).length != 0) links = string.concat(" Website: ", website);
        if (bytes(xLink).length != 0) links = string.concat(links, " X: ", xLink);
        string memory json = string.concat('{"name":"PEPES FAMILY","description":"', description, links, '"');
        if (bytes(collectionImage).length != 0) {
            json = string.concat(json, ',"image":"', collectionImage, '","featured_image":"', collectionImage, '"');
        }
        if (bytes(bannerImage).length != 0) json = string.concat(json, ',"banner_image":"', bannerImage, '"');
        if (bytes(website).length != 0) json = string.concat(json, ',"external_link":"', website, '"');
        json = string.concat(json, "}");
        return string.concat("data:application/json;base64,", FastBase64.encode(bytes(json)));
    }

    /// @notice Every Pepe `owner` holds, without scanning event logs.
    function tokensOfOwner(address owner) external view returns (uint256[] memory ids) {
        uint256 n = balanceOf(owner);
        ids = new uint256[](n);
        uint256 found;
        for (uint256 id = 1; id <= totalMinted && found < n; id++) {
            if (_ownerOf(id) == owner) ids[found++] = id;
        }
    }

    // ---------------------------------------------------------------- royalty enforcement

    function getTransferValidator() external view returns (address) {
        return transferValidator;
    }

    function getTransferValidationFunction() external pure returns (bytes4 functionSignature, bool isViewFunction) {
        return (VALIDATE_TRANSFER, true);
    }

    /// @notice Point the collection at a new validator, e.g. if marketplaces move to a new registry. It must be a
    ///         contract, so the collection always names one; but the owner can relax enforcement, plainly: a validator
    ///         that allows everything lets marketplaces skip the royalty. Any change shows on chain
    ///         (`TransferValidatorUpdated`). The 5% rate itself never changes.
    function setTransferValidator(address validator) external onlyOwner {
        _setValidator(validator);
    }

    function _setValidator(address validator) private {
        if (validator.code.length == 0) revert NotAContract();
        emit TransferValidatorUpdated(transferValidator, validator);
        transferValidator = validator;
    }

    /// @dev Mints skip the check; every transfer between wallets goes through the validator.
    function _update(address to, uint256 tokenId, address auth) internal override returns (address) {
        address from = _ownerOf(tokenId);
        if (from != address(0) && to != address(0)) {
            ITransferValidator721(transferValidator).validateTransfer(msg.sender, from, to, tokenId);
        }
        return super._update(to, tokenId, auth);
    }

    // ---------------------------------------------------------------- admin

    /// @notice Open or close the mint (a pause until the reveal). Never again once the secret is public (`reveal`).
    function setSaleOpen(bool open) external onlyOwner {
        if (entropyBlock != 0) revert AlreadyRevealed();
        saleOpen = open;
        emit SaleOpen(open);
    }

    /// @notice The price of one Pepe in wei; 0 makes the mint free. (Priced in ETH: to keep it near $1, set it again
    ///         when ETH's price moves.)
    function setPrice(uint256 price_) external onlyOwner {
        price = price_;
        emit PriceSet(price_);
    }

    /// @notice How many Pepes one wallet can mint in all (1 to MAX_WALLET_LIMIT).
    function setWalletLimit(uint256 limit) external onlyOwner {
        if (limit == 0 || limit > MAX_WALLET_LIMIT) revert BadWalletLimit();
        walletLimit = limit;
        emit WalletLimitSet(limit);
    }

    /// @notice Moves mint payments and the royalty together. The 5% rate never changes. The new treasury must take
    ///         ETH: it is sent a plain call with no ETH first, and refused if that fails.
    function setTreasury(address treasury_) external onlyOwner {
        _checkTreasury(treasury_);
        treasury = treasury_;
        _setDefaultRoyalty(treasury_, ROYALTY_BPS);
        emit TreasurySet(treasury_);
    }

    function _checkTreasury(address treasury_) private {
        if (treasury_ == address(0)) revert ZeroAddress();
        if (treasury_ == address(this)) revert BadTreasury();
        bool ok;
        assembly ("memory-safe") {
            ok := call(gas(), treasury_, 0, 0, 0, 0, 0)
        }
        if (!ok) revert TreasuryRefusesEth();
    }

    /// @notice The project's website (the collection's link on marketplaces, and each Pepe's external_url) and its X
    ///         link (in the collection's description), at any time; "" leaves one out. Plain URLs only: no quotes,
    ///         backslashes or control characters, at most MAX_LINK bytes.
    function setLinks(string calldata website_, string calldata xLink_) external onlyOwner {
        _checkText(website_, MAX_LINK);
        _checkText(xLink_, MAX_LINK);
        website = website_;
        xLink = xLink_;
        emit LinksSet(website_, xLink_);
        emit ContractURIUpdated();
        if (totalMinted != 0) emit BatchMetadataUpdate(1, totalMinted);
    }

    /// @notice The collection's picture and banner on marketplaces (https:// or ipfs:// URLs), at any time; "" leaves
    ///         one out. Same rules as the links.
    function setCollectionImages(string calldata image, string calldata banner) external onlyOwner {
        _checkText(image, MAX_LINK);
        _checkText(banner, MAX_LINK);
        collectionImage = image;
        bannerImage = banner;
        emit CollectionImagesSet(image, banner);
        emit ContractURIUpdated();
    }

    /// @notice The collection's description (also each revealed Pepe's), at any time: at most MAX_DESCRIPTION bytes,
    ///         no quotes, backslashes or control characters.
    function setDescription(string calldata description_) external onlyOwner {
        _checkText(description_, MAX_DESCRIPTION);
        description = description_;
        emit DescriptionSet(description_);
        emit ContractURIUpdated();
        if (totalMinted != 0) emit BatchMetadataUpdate(1, totalMinted);
    }

    function _checkText(string calldata text, uint256 max) private pure {
        bytes calldata b = bytes(text);
        if (b.length > max) revert BadLink();
        for (uint256 i; i < b.length; ++i) {
            bytes1 c = b[i];
            if (c < 0x20 || c == 0x7f || c == '"' || c == "\\") revert BadLink();
        }
    }

    /// @notice Ask marketplaces to re-read Pepes `fromTokenId` to `toTokenId` (ERC-4906). The owner only.
    function refreshMetadata(uint256 fromTokenId, uint256 toTokenId) external onlyOwner {
        if (toTokenId > totalMinted) toTokenId = totalMinted;
        if (fromTokenId == 0) fromTokenId = 1;
        if (fromTokenId > toTokenId) return;
        if (fromTokenId == toTokenId) emit MetadataUpdate(fromTokenId);
        else emit BatchMetadataUpdate(fromTokenId, toTokenId);
    }

    /// @notice Point the collection's metadata somewhere else (a JSON URL), or back to the built-in one ("").
    function setContractURI(string calldata uri) external onlyOwner {
        customContractURI = uri;
        emit ContractURIUpdated();
    }

    /// @notice Ownership can't be renounced (a renounced owner could never update the links, the price or the
    ///         validator again, nor edit the collection in OpenSea Studio, which lets only owner() do that). It can be
    ///         handed over in two steps: only ever to a wallet that can sign in to OpenSea Studio.
    function renounceOwnership() public view override onlyOwner {
        revert CannotRenounce();
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, ERC2981) returns (bool) {
        return interfaceId == type(ICreatorToken).interfaceId || interfaceId == bytes4(0x49064906) // ERC-4906
            || super.supportsInterface(interfaceId);
    }
}
