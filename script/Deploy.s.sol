// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {PepesFamily} from "../src/PepesFamily.sol";
import {ImdPepeArt, IImdPepeSpecs} from "../src/ImdPepeArt.sol";
import {ImdPepeSpecs} from "../src/ImdPepeSpecs.sol";
import {ImdPepeParts} from "../src/ImdPepeParts.sol";
import {ImdPepeData0} from "../src/ImdPepeData0.sol";
import {ImdPepeData1} from "../src/ImdPepeData1.sol";
import {ImdPepeData2} from "../src/ImdPepeData2.sol";
import {ImdPepeData3} from "../src/ImdPepeData3.sol";
import {ImdPepeData4} from "../src/ImdPepeData4.sol";
import {ImdPepeData5} from "../src/ImdPepeData5.sol";
import {ImdPepeData6} from "../src/ImdPepeData6.sol";

interface VmDeploy {
    function envAddress(string calldata name) external view returns (address);
    function envUint(string calldata name) external view returns (uint256);
    function envBytes32(string calldata name) external view returns (bytes32);
    function envOr(string calldata name, address defaultValue) external view returns (address);
    function envOr(string calldata name, string calldata defaultValue) external view returns (string memory);
    function envOr(string calldata name, bool defaultValue) external view returns (bool);
    function startBroadcast(address signer) external;
    function stopBroadcast() external;
}

/// @notice Deploys Pepes Family in one session (one browser-wallet connection for every transaction): the art
///         contracts, the collection, then optionally its website link and the open mint. Settings come from
///         environment variables:
///         OWNER, PRICE_WEI, COMMIT (hash of the reveal secret), VALIDATOR, and optionally SPECS (an ImdPepeSpecs
///         already deployed, reused), WEBSITE, X_LINK and OPEN_SALE. The addresses are in Foundry's broadcast record
///         (broadcast/Deploy.s.sol/<chain>/run-latest.json). The mainnet deploy (2026-10-18) ran:
///           COMMIT=<hash of the reveal secret> OWNER=<owner> PRICE_WEI=413000000000000 VALIDATOR=<OpenSea's> \
///           SPECS=<ImdPepeSpecs> WEBSITE=https://pepesfamily.fun OPEN_SALE=true forge script script/Deploy.s.sol \
///           --rpc-url https://robinhood.drpc.org --sender <owner> --broadcast --slow --browser --browser-port 9545
contract Deploy {
    VmDeploy constant vm = VmDeploy(address(uint160(uint256(keccak256("hevm cheat code")))));

    function run() external returns (address pepesAddr, address artAddr) {
        address owner = vm.envAddress("OWNER");
        address validator = vm.envAddress("VALIDATOR");
        address specs = vm.envOr("SPECS", address(0));
        require(specs == address(0) || specs.code.length != 0, "SPECS has no code");
        require(validator.code.length != 0, "VALIDATOR has no code");

        vm.startBroadcast(owner); // the connected wallet must be the owner (OpenSea lets only owner() edit the collection)
        ImdPepeArt art = _art(specs);
        PepesFamily pepes = new PepesFamily(owner, owner, vm.envUint("PRICE_WEI"), vm.envBytes32("COMMIT"), validator, art);
        string memory website = vm.envOr("WEBSITE", string(""));
        string memory xLink = vm.envOr("X_LINK", string(""));
        if (bytes(website).length != 0 || bytes(xLink).length != 0) pepes.setLinks(website, xLink);
        if (vm.envOr("OPEN_SALE", false)) pepes.setSaleOpen(true);
        vm.stopBroadcast();
        return (address(pepes), address(art));
    }

    /// @dev The art: the trait sets (unless already deployed), the text, the 7 frame contracts, then ImdPepeArt.
    function _art(address specs) private returns (ImdPepeArt) {
        if (specs == address(0)) specs = address(new ImdPepeSpecs());
        address parts = address(new ImdPepeParts());
        address[7] memory d = [
            address(new ImdPepeData0()), address(new ImdPepeData1()), address(new ImdPepeData2()), address(new ImdPepeData3()),
            address(new ImdPepeData4()), address(new ImdPepeData5()), address(new ImdPepeData6())
        ];
        return new ImdPepeArt(IImdPepeSpecs(specs), parts, d[0], d[1], d[2], d[3], d[4], d[5], d[6]);
    }
}
