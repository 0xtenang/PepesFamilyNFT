// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ImdPepeArt} from "../src/ImdPepeArt.sol";
import {ImdArt} from "../test/utils/ImdArt.sol";

interface VmPreview {
    function writeFile(string calldata path, string calldata data) external;
    function envOr(string calldata name, uint256 defaultValue) external view returns (uint256);
}

/// Writes build/preview/<index>.svg for trait sets FROM to FROM + COUNT (default the first 48), and sealed.svg, as
/// the contracts draw them. Nothing is sent anywhere:
///   forge script script/Preview.s.sol
contract Preview {
    VmPreview constant vm = VmPreview(address(uint160(uint256(keccak256("hevm cheat code")))));

    function run() external {
        ImdPepeArt art = ImdArt.deploy();
        uint256 from = vm.envOr("FROM", uint256(0));
        uint256 count = vm.envOr("COUNT", uint256(48));
        vm.writeFile("build/preview/sealed.svg", art.sealedSvg());
        for (uint256 i = from; i < from + count && i < 3333; ++i) {
            vm.writeFile(string.concat("build/preview/", _str(i), ".svg"), art.render(i));
            vm.writeFile(string.concat("build/preview/", _str(i), ".json"), art.attributes(i));
        }
    }

    function _str(uint256 v) private pure returns (string memory s) {
        if (v == 0) return "0";
        while (v != 0) { s = string.concat(string(abi.encodePacked(bytes1(uint8(48 + v % 10)))), s); v /= 10; }
    }
}
