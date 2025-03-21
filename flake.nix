{
  description = "Python environment with pynput";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: {
    devShells.x86_64-linux.default = let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
    in pkgs.mkShell {
      buildInputs = [
        (pkgs.python3.withPackages (ps: with ps; [
          pynput
          humanize
        ]))
      ];

      shellHook = ''
        alias python=python3
      '';
    };
  };
}
