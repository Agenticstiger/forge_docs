# FLUID Forge Contract GPT Packet

> **Building a custom GPT or plugin around Fluid Forge?** This section collects the artifacts you need to spin one up: the FLUID 0.7.2 schema knowledge file, validation reference, plan reference, conversation starters, and the upload manifest. **End users running `fluid forge` from the CLI can safely skip this section** — those workflows live under [`fluid forge`](/cli/forge.html) and the [Forge Copilot guides](/advanced/forge-copilot-discovery).

---

This folder is a self-contained builder packet for a ChatGPT custom GPT (or other plugin) that drafts and reviews FLUID Forge contracts.

It is designed around these rules:

- Default to FLUID `0.7.2`
- Ask for provider before drafting
- Output `contract.fluid.yaml` first
- Add `Assumptions`, `Open questions`, and `Validation next steps`
- Treat every response as `Draft` until `fluid validate --strict` and `fluid plan --json` have been reviewed

## What To Use

Use these files in the GPT builder:

- `GPT_INSTRUCTIONS.md`: paste into the GPT Instructions field
- `CONVERSATION_STARTERS.md`: paste into Conversation starters
- `CHATGPT_BUILDER_CHECKLIST.md`: follow this while configuring the GPT
- `UPLOAD_MANIFEST.md`: use this to upload the curated knowledge pack

Upload these as GPT knowledge:

- `FORGE_GPT_STYLE_GUIDE.md`
- `FORGE_GPT_REVIEW_CHECKLIST.md`
- `FORGE_GPT_FEW_SHOTS.md`
- Everything in `knowledge/`

## Source Material

This packet is documented in `forge_docs`, but it was grounded in source-of-truth assets from the sibling `forge-cli` repository:

- `forge-cli/fluid_build/schemas/fluid-schema-0.7.2.json`
- `forge-cli/README.md`
- `forge-cli/examples/01-hello-world/contract.fluid.yaml`
- `forge-cli/examples/05-data-quality-validation/contract.fluid.yaml`
- `forge-cli/examples/customer360/contract.fluid.yaml`
- `forge_docs/docs/cli/validate.md`
- `forge_docs/docs/cli/plan.md`

## Quick Start

1. Open ChatGPT and create a new GPT in configuration view.
2. Paste `GPT_INSTRUCTIONS.md` into Instructions.
3. Add the starters from `CONVERSATION_STARTERS.md`.
4. Upload the files listed in `UPLOAD_MANIFEST.md`.
5. Keep the GPT private or workspace-only.
6. Preview with the smoke tests in `CHATGPT_BUILDER_CHECKLIST.md`.

This packet does not create the GPT automatically in ChatGPT. It gives you the exact builder inputs and upload set so the GPT can be created quickly and consistently.
