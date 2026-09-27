"""Summary of a GGUF: architecture, context, KV, vision/audio, MTP, thinking.

Answers at a glance the questions to check BEFORE writing a new launcher profile
(see ../AGENTS.md):
  - which architecture it is (and whether the engine supports it)
  - native context, how many layers actually carry KV (cheap vs. expensive KV)
  - whether it's multimodal (vision / audio), or whether the file itself IS an mmproj
  - whether it ships MTP (nextn) heads -> --spec-type draft-mtp can be tried
  - whether it reasons, and with which kwarg (enable_thinking vs. preserve_thinking)
  - sampling recommended by the model itself (general.sampling.*)

Usage:
    python3 scripts/gguf_info.py /path/to/Models/<model>/<file>.gguf
    python3 scripts/gguf_info.py /path/to/Models              # walks all of them
"""
import argparse
import pathlib
import sys


def describe(path: pathlib.Path) -> bool:
    try:
        size = path.stat().st_size
    except OSError as e:
        print(f"{path}: [ERROR] could not stat file: {e}", file=sys.stderr)
        return False
    print("=" * 78)
    print(path.name, f"({size / 2**30:.2f} GB)")
    try:
        from gguf import GGUFReader
    except ImportError as e:
        print(
            "ERROR: gguf_info.py requires the 'gguf' package. Install it with "
            "`python3 -m pip install gguf`.",
            file=sys.stderr,
        )
        return False
    try:
        r = GGUFReader(str(path))
    except Exception as e:
        print(f"  [ERROR] could not read: {e}", file=sys.stderr)
        return False
    kv = {}
    for f in r.fields.values():
        try:
            kv[f.name] = f.contents()
        except Exception:
            pass

    arch = kv.get("general.architecture", "?")
    gtype = kv.get("general.type", "model")
    print(f"  architecture : {arch}   type: {gtype}")
    if kv.get("general.name"):
        print(f"  name         : {kv['general.name']}")
    if kv.get("general.license"):
        print(f"  license      : {kv['general.license']}")

    # --- It's a multimodal projector, not a model ---
    if gtype == "mmproj" or arch == "clip":
        mods = []
        if kv.get("clip.has_vision_encoder") or any("clip.vision" in k for k in kv):
            mods.append("VISION")
        if any("clip.audio" in k for k in kv):
            mods.append("AUDIO")
        print(f"  >>> This is an MMPROJ (projector), NOT a model. Modalities: {', '.join(mods) or '?'}")
        print("      Pass it with --mmproj ALONGSIDE the main model.")
        return

    n_layer = kv.get(f"{arch}.block_count")
    ctx = kv.get(f"{arch}.context_length")
    print(f"  layers       : {n_layer}    native context: {ctx}")

    # --- KV: how many layers actually carry it ---
    kvh = kv.get(f"{arch}.attention.head_count_kv")
    interval = kv.get(f"{arch}.full_attention_interval")
    swa = kv.get(f"{arch}.attention.sliding_window_pattern")
    if isinstance(kvh, list):
        att = sum(1 for x in kvh if x)
        print(f"  CHEAP KV     : only {att} of {len(kvh)} layers have attention (rest is conv/SSM)")
    elif interval:
        print(f"  CHEAP KV     : full_attention_interval={interval} -> "
              f"~{(n_layer or 0)//interval} of {n_layer} layers carry KV")
    elif isinstance(swa, list):
        glob = sum(1 for x in swa if not x)
        print(f"  MIXED KV     : {glob} global layers + {len(swa)-glob} sliding-window")
    kl = kv.get(f"{arch}.attention.key_length")
    if kl:
        print(f"  key_length   : {kl}" + ("  <- LARGE, KV is expensive per global layer" if kl >= 512 else ""))

    # --- MoE ---
    if kv.get(f"{arch}.expert_count"):
        print(f"  MoE          : {kv[f'{arch}.expert_count']} experts, "
              f"{kv.get(f'{arch}.expert_used_count','?')} active -> use --cpu-moe")

    # --- MTP (multi-token prediction) ---
    mtp_keys = [k for k in kv if "nextn" in k.lower() or "mtp" in k.lower()]
    if mtp_keys:
        print(f"  MTP          : YES -> can try --spec-type draft-mtp "
              f"(-np 1; combine with --mmproj if needed, see models.toml). Keys: {mtp_keys}")
    else:
        print("  MTP          : not detected (no nextn/mtp keys)")

    # --- Thinking ---
    tpl = kv.get("tokenizer.chat_template", "")
    if isinstance(tpl, str) and tpl:
        if "<think>" in tpl:
            kwarg = ("enable_thinking" if "enable_thinking" in tpl else
                     "preserve_thinking" if "preserve_thinking" in tpl else "?")
            print(f"  thinking     : uses <think> (kwarg: {kwarg}) -> no flags needed, the "
                  "default --reasoning-format auto already separates it")
        elif "channel" in tpl.lower():
            print("  thinking     : CHANNEL format (Gemma-4 style) -> no flags. "
                  "NEVER --reasoning-format deepseek, it parses this wrong")
        else:
            print("  thinking     : no <think> in the template")

    # --- Model-recommended sampling ---
    samp = {k.split(".")[-1]: v for k, v in kv.items() if k.startswith("general.sampling.")}
    if samp:
        print(f"  GGUF sampling: {samp}   <- use THESE, not another family's")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=pathlib.Path, help="GGUF file or directory to inspect")
    args = parser.parse_args(argv)
    target = args.path
    try:
        is_dir = target.is_dir()
    except OSError as e:
        print(f"ERROR: could not inspect {target}: {e}", file=sys.stderr)
        return 1
    try:
        files = sorted(target.rglob("*.gguf")) if is_dir else [target]
    except OSError as e:
        print(f"ERROR: could not list {target}: {e}", file=sys.stderr)
        return 1
    if not files:
        print(f"ERROR: no .gguf in {target}", file=sys.stderr)
        return 1
    succeeded = True
    for path in files:
        if not describe(path):
            succeeded = False
    return 0 if succeeded else 1


if __name__ == "__main__":
    sys.exit(main())


