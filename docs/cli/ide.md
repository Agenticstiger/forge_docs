# `fluid ide`

IDE integration and developer experience features — generate a VS Code extension scaffold, install shell completion, and serve language-server completions and diagnostics.

## Syntax

```bash
fluid ide ACTION [SUBACTION] [...]
```

## Key options

| Option | Description |
| --- | --- |
| `setup [--ide {vscode,intellij,pycharm,vim,emacs,sublime}]` | Set up IDE integration (default `vscode`). Currently only the VS Code path is implemented. |
| `lsp start [--port PORT]` | Start the FLUID Language Server (default port `9257`). |
| `lsp completions FILE LINE COLUMN` | Print JSON-formatted completion suggestions for a position in a file. |
| `completion [--shell {bash,zsh,fish}]` | Install a shell completion script (default `bash`). |
| `validate FILE` | Run the IDE-style validator against a file and print diagnostics in a table. |

## Examples

```bash
fluid ide setup --ide vscode
fluid ide completion --shell zsh
fluid ide lsp completions contract.fluid.yaml 12 4
fluid ide validate contract.fluid.yaml
```

## Notes

- The VS Code scaffold is written under `~/.fluid/ide/vscode-extension/` (`package.json`, `language-configuration.json`, `src/extension.ts`, `tsconfig.json`). After it's created, run `npm install` and `npm run compile` to build the extension before installing.
- Bash completion is installed at `~/.bash_completion.d/fluid`; zsh completion at `~/.zsh/completions/_fluid` (you may need to add `fpath=(~/.zsh/completions $fpath)` to `~/.zshrc`).
- All output requires the `rich` library — without it the subcommands print a one-line "requires rich library" message and exit with code 1.
- The `lsp start` subcommand is currently a placeholder — it prints status messages but does not yet serve a real Language Server Protocol session.
- For project setup that doesn't depend on an IDE, see [`fluid init`](./init.md) and [`fluid doctor`](./doctor.md).
