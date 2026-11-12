{
  description = "Native tools for Nexigon Yocto development";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  outputs = { nixpkgs, ... }: {
    checks = nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-linux" ] (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        scripts =
          pkgs.runCommand "check-development-scripts"
            {
              nativeBuildInputs = [ pkgs.shellcheck ];
            }
            ''
              shellcheck ${./scripts/kas.sh} ${./scripts/run-qemu.sh} ${./scripts/test.sh} ${./scripts/generate-rauc-keys.sh}
              touch "$out"
            '';
      }
    );
    devShells = nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-linux" ] (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        default = pkgs.mkShell {
          packages = with pkgs; [
            qemu
            shellcheck
          ];
        };
      }
    );
  };
}
