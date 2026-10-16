// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/// @notice The few Forge cheatcodes the tests use (a subset of forge-std's Vm).
interface Vm {
    function prank(address sender, address origin) external;
    function startPrank(address sender, address origin) external;
    function stopPrank() external;
    function deal(address who, uint256 amount) external;
    function roll(uint256 blockNumber) external;
    function expectRevert(bytes4 selector) external;
    function expectRevert(bytes calldata revertData) external;
    function expectRevert() external;
    function addr(uint256 privateKey) external returns (address);
    function etch(address target, bytes calldata code) external;
    function readFile(string calldata path) external view returns (string memory);
}

/// @notice A minimal test base: the cheatcodes and a few assertions.
abstract contract MiniTest {
    Vm internal constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    error AssertionFailed(string what);

    function assertTrue(bool ok, string memory what) internal pure {
        if (!ok) revert AssertionFailed(what);
    }

    function assertEq(uint256 a, uint256 b, string memory what) internal pure {
        if (a != b) revert AssertionFailed(what);
    }

    function assertEq(address a, address b, string memory what) internal pure {
        if (a != b) revert AssertionFailed(what);
    }

    function assertEq(string memory a, string memory b, string memory what) internal pure {
        if (keccak256(bytes(a)) != keccak256(bytes(b))) revert AssertionFailed(what);
    }

    /// @dev Whether `needle` appears in `hay`.
    function contains(string memory hay, string memory needle) internal pure returns (bool) {
        bytes memory h = bytes(hay);
        bytes memory n = bytes(needle);
        if (n.length > h.length) return false;
        for (uint256 i; i + n.length <= h.length; ++i) {
            bool ok = true;
            for (uint256 j; j < n.length; ++j) {
                if (h[i + j] != n[j]) {
                    ok = false;
                    break;
                }
            }
            if (ok) return true;
        }
        return false;
    }

    function startsWith(string memory s, string memory prefix) internal pure returns (bool) {
        bytes memory a = bytes(s);
        bytes memory p = bytes(prefix);
        if (p.length > a.length) return false;
        for (uint256 i; i < p.length; ++i) {
            if (a[i] != p[i]) return false;
        }
        return true;
    }
}
