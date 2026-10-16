// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {MiniTest} from "./utils/MiniTest.sol";
import {PepesFamily} from "../src/PepesFamily.sol";
import {FrogCraftArt, IFrogCraftSpecs} from "../src/FrogCraftArt.sol";
import {FrogCraftArtData} from "../src/FrogCraftArtData.sol";
import {FrogCraftSpecs} from "../src/FrogCraftSpecs.sol";
import {DevTransferValidator} from "../script/DevTransferValidator.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

contract RefusesEth {}

contract MinterContract {
    function mint(PepesFamily p) external {
        p.mint(1);
    }
}

contract PepesFamilyTest is MiniTest {
    address constant OWNER = 0x3c8A4d94B3219F6633F2cC94094f4765b30c691C;
    uint256 constant SECRET = 0xC0FFEE;
    uint256 constant PRICE = 0.00025 ether;

    PepesFamily pepes;
    FrogCraftArt art;
    DevTransferValidator validator;
    address alice = address(0xA11CE);
    address bob = address(0xB0B);

    function setUp() public {
        art = new FrogCraftArt(IFrogCraftSpecs(address(new FrogCraftSpecs())), address(new FrogCraftArtData()));
        validator = new DevTransferValidator();
        pepes = new PepesFamily(OWNER, OWNER, PRICE, keccak256(abi.encode(SECRET)), address(validator), art);
        vm.deal(alice, 10 ether);
        vm.deal(bob, 10 ether);
    }

    function _open() internal {
        vm.prank(OWNER, OWNER);
        pepes.setSaleOpen(true);
    }

    function _mint(address who, uint256 n) internal {
        vm.prank(who, who);
        pepes.mint{value: PRICE * n}(n);
    }

    function _reveal() internal {
        vm.startPrank(OWNER, OWNER);
        pepes.setSaleOpen(false);
        pepes.reveal(SECRET);
        vm.stopPrank();
        vm.roll(block.number + 2);
        pepes.seal();
    }

    function test_TheCollection() public view {
        assertEq(pepes.name(), "PEPES FAMILY", "name");
        assertEq(pepes.symbol(), "PEPES", "symbol");
        assertEq(pepes.owner(), OWNER, "owner");
        assertEq(pepes.treasury(), OWNER, "treasury");
        assertEq(pepes.price(), PRICE, "price");
        assertEq(pepes.walletLimit(), 3, "wallet limit");
        assertEq(pepes.MAX_SUPPLY(), 3333, "supply");
        (address to, uint256 fee) = pepes.royaltyInfo(1, 1 ether);
        assertEq(to, OWNER, "royalty receiver");
        assertEq(fee, 0.05 ether, "royalty 5%");
        assertTrue(pepes.supportsInterface(0x2a55205a), "ERC-2981");
        assertTrue(pepes.supportsInterface(0x80ac58cd), "ERC-721");
        assertTrue(pepes.supportsInterface(0x49064906), "ERC-4906");
        assertEq(pepes.getTransferValidator(), address(validator), "validator");
    }

    function test_PaidMintPaysTheTreasury() public {
        _open();
        uint256 before = OWNER.balance;
        _mint(alice, 2);
        assertEq(OWNER.balance - before, 2 * PRICE, "treasury paid");
        assertEq(address(pepes).balance, 0, "holds nothing");
        assertEq(pepes.ownerOf(1), alice, "#1");
        assertEq(pepes.ownerOf(2), alice, "#2");
    }

    function test_MintRules() public {
        vm.prank(alice, alice);
        vm.expectRevert(PepesFamily.SaleClosed.selector);
        pepes.mint{value: PRICE}(1);
        _open();
        vm.prank(alice, alice);
        vm.expectRevert(PepesFamily.WrongPayment.selector);
        pepes.mint{value: PRICE - 1}(1);
        vm.prank(alice, alice);
        vm.expectRevert(PepesFamily.BadQuantity.selector);
        pepes.mint(0);
        vm.prank(alice, alice);
        vm.expectRevert(PepesFamily.WalletLimit.selector);
        pepes.mint{value: PRICE * 4}(4);
        _mint(alice, 3);
        vm.prank(alice, alice);
        vm.expectRevert(PepesFamily.WalletLimit.selector);
        pepes.mint{value: PRICE}(1);
        assertEq(pepes.balanceOf(alice), 3, "three");
    }

    function test_AContractCantMint() public {
        _open();
        MinterContract c = new MinterContract();
        vm.prank(address(c), alice);
        vm.expectRevert(PepesFamily.OnlyWallets.selector);
        pepes.mint(1);
    }

    function test_SellsOutAt3333AndEveryTokenGetsADifferentTraitSet() public {
        vm.startPrank(OWNER, OWNER);
        pepes.setSaleOpen(true);
        pepes.setPrice(0);
        pepes.setWalletLimit(50);
        vm.stopPrank();
        for (uint256 i; i < 67; ++i) {
            address w = vm.addr(1000 + i);
            for (uint256 k; k < 10 && pepes.totalMinted() < 3333; ++k) {
                uint256 n = 3333 - pepes.totalMinted();
                if (n > 5) n = 5;
                vm.prank(w, w);
                pepes.mint(n);
            }
        }
        assertEq(pepes.totalMinted(), 3333, "sold out");
        address late = vm.addr(9999);
        vm.prank(late, late);
        vm.expectRevert(PepesFamily.SoldOut.selector);
        pepes.mint(1);
        _reveal();
        uint256[14] memory seen; // a bit per trait set
        for (uint256 id = 1; id <= 3333; ++id) {
            uint256 s = pepes.traitSetOf(id);
            assertTrue(s < 3333, "in range");
            uint256 bit = 1 << (s % 256);
            assertTrue(seen[s / 256] & bit == 0, "no two alike");
            seen[s / 256] |= bit;
        }
    }

    function test_RevealNeedsTheSecretAndEndsTheSale() public {
        _open();
        _mint(alice, 1);
        vm.prank(OWNER, OWNER);
        vm.expectRevert(PepesFamily.SaleStillOpen.selector);
        pepes.reveal(SECRET);
        vm.startPrank(OWNER, OWNER);
        pepes.setSaleOpen(false);
        vm.expectRevert(PepesFamily.BadSecret.selector);
        pepes.reveal(SECRET + 1);
        pepes.reveal(SECRET);
        vm.expectRevert(PepesFamily.AlreadyRevealed.selector);
        pepes.setSaleOpen(true);
        vm.stopPrank();
        vm.expectRevert(PepesFamily.RevealTooSoon.selector);
        pepes.seal();
        vm.roll(block.number + 2);
        vm.prank(bob, bob); // anyone can seal
        pepes.seal();
        assertTrue(pepes.seed() != 0, "sealed");
        assertEq(uint256(pepes.revealStatus()), uint256(PepesFamily.RevealStatus.Revealed), "revealed");
    }

    function test_TokenURIBeforeAndAfterReveal() public {
        _open();
        _mint(alice, 1);
        string memory sealedUri = pepes.tokenURI(1);
        assertTrue(startsWith(sealedUri, "data:application/json;base64,"), "sealed json");
        vm.expectRevert(PepesFamily.NotRevealed.selector);
        pepes.traitSetOf(1);
        _reveal();
        string memory uri = pepes.tokenURI(1);
        assertTrue(startsWith(uri, "data:application/json;base64,"), "json");
        assertTrue(keccak256(bytes(uri)) != keccak256(bytes(sealedUri)), "revealed");
        string memory attrs = art.attributes(pepes.traitSetOf(1));
        assertTrue(contains(attrs, '"trait_type":"Background"'), "background trait");
        assertTrue(startsWith(art.render(pepes.traitSetOf(1)), "<svg"), "svg");
        assertEq(pepes.skinPixels(1).length, 16384, "skin");
    }

    function test_OwnerUpdatesTheLinksAnyTime() public {
        vm.prank(OWNER, OWNER);
        pepes.setLinks("https://pepesfamily.xyz", "https://x.com/pepesfamily");
        assertEq(pepes.website(), "https://pepesfamily.xyz", "website");
        assertEq(pepes.xLink(), "https://x.com/pepesfamily", "x");
        vm.prank(OWNER, OWNER);
        pepes.setDescription("New words.");
        assertEq(pepes.description(), "New words.", "description");
        vm.prank(OWNER, OWNER);
        pepes.setCollectionImages("https://pepesfamily.xyz/logo.png", "https://pepesfamily.xyz/banner.png");
        assertTrue(startsWith(pepes.contractURI(), "data:application/json;base64,"), "contractURI");
        // still after selling out and revealing
        _open();
        _mint(alice, 1);
        _reveal();
        vm.prank(OWNER, OWNER);
        pepes.setLinks("https://pepes.family", "https://x.com/pepes");
        assertEq(pepes.website(), "https://pepes.family", "later");
    }

    function test_LinksThatWouldBreakTheJsonAreRefused() public {
        vm.startPrank(OWNER, OWNER);
        vm.expectRevert(PepesFamily.BadLink.selector);
        pepes.setLinks('https://a"b', "");
        vm.expectRevert(PepesFamily.BadLink.selector);
        pepes.setLinks("", "https://x.com/\\");
        vm.expectRevert(PepesFamily.BadLink.selector);
        pepes.setDescription("line\nbreak");
        vm.stopPrank();
    }

    function test_OwnerOnly() public {
        vm.startPrank(alice, alice);
        bytes memory e = abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, alice);
        vm.expectRevert(e);
        pepes.setLinks("https://a", "https://b");
        vm.expectRevert(e);
        pepes.setDescription("x");
        vm.expectRevert(e);
        pepes.setSaleOpen(true);
        vm.expectRevert(e);
        pepes.setPrice(0);
        vm.expectRevert(e);
        pepes.setTreasury(alice);
        vm.expectRevert(e);
        pepes.setTransferValidator(address(validator));
        vm.expectRevert(e);
        pepes.reveal(SECRET);
        vm.stopPrank();
    }

    function test_RenounceRevertsAndOwnershipMovesInTwoSteps() public {
        vm.prank(OWNER, OWNER);
        vm.expectRevert(PepesFamily.CannotRenounce.selector);
        pepes.renounceOwnership();
        vm.prank(OWNER, OWNER);
        pepes.transferOwnership(bob);
        assertEq(pepes.owner(), OWNER, "not yet");
        vm.prank(bob, bob);
        pepes.acceptOwnership();
        assertEq(pepes.owner(), bob, "moved");
    }

    function test_RoyaltyEnforcedButHoldersMoveTheirOwn() public {
        _open();
        _mint(alice, 2);
        vm.prank(alice, alice);
        pepes.transferFrom(alice, bob, 1); // a holder moving its own
        assertEq(pepes.ownerOf(1), bob, "moved");
        vm.prank(alice, alice);
        pepes.setApprovalForAll(address(this), true);
        // a marketplace the validator doesn't authorize can't move it
        vm.expectRevert(DevTransferValidator.UnauthorizedTransfer.selector);
        pepes.transferFrom(alice, bob, 2);
        vm.prank(OWNER, OWNER);
        vm.expectRevert(PepesFamily.NotAContract.selector);
        pepes.setTransferValidator(address(0));
    }

    function test_TreasuryMustTakeEth() public {
        RefusesEth r = new RefusesEth();
        vm.prank(OWNER, OWNER);
        vm.expectRevert(PepesFamily.TreasuryRefusesEth.selector);
        pepes.setTreasury(address(r));
        vm.prank(OWNER, OWNER);
        pepes.setTreasury(bob);
        (address to,) = pepes.royaltyInfo(1, 100);
        assertEq(to, bob, "royalty follows the treasury");
    }

    function test_TheFourOneOfOnesAreInTheSet() public view {
        for (uint256 i; i < 4; ++i) {
            assertTrue(contains(art.attributes(i), '"trait_type":"1/1"'), "1/1");
        }
        assertTrue(!contains(art.attributes(4), '"trait_type":"1/1"'), "not a 1/1");
    }
}
