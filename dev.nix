{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python39  # 指定 Python 版本为 3.9
    pkgs.python39.pkgs.redis
    pkgs.python39.pkgs.lxml
    pkgs.python39.pkgs.aioredis
    pkgs.python39.pkgs.aiohttp
    pkgs.python39.pkgs.httpx
    pkgs.python39.pkgs.rich
    pkgs.python39.pkgs.typer
  ];
}
