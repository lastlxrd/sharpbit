from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT = Path(__file__).resolve().parent
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from sharpbit_core import convert_all  # noqa: E402

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None


def split_dnd_paths(data: str) -> list[str]:
    items: list[str] = []
    current = ""
    in_braces = False
    for char in data:
        if char == "{":
            in_braces = True
            current = ""
            continue
        if char == "}":
            in_braces = False
            if current:
                items.append(current)
                current = ""
            continue
        if char == " " and not in_braces:
            if current:
                items.append(current)
                current = ""
            continue
        current += char
    if current:
        items.append(current)
    return items


class SharpBitGUI:
    def __init__(self) -> None:
        self.root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
        self.root.title("SharpBit")
        self.root.geometry("760x620")
        self.root.minsize(720, 560)

        self.sources: list[Path] = []

        self.dither_var = tk.StringVar(value="bayer4")
        self.threshold_var = tk.StringVar(value="128")
        self.fit_var = tk.StringVar(value="contain")
        self.display_w_var = tk.StringVar(value="400")
        self.display_h_var = tk.StringVar(value="240")
        self.bit_order_var = tk.StringVar(value="msb")
        self.black_bit_var = tk.StringVar(value="1")
        self.video_fps_var = tk.StringVar(value="10")
        self.max_frames_var = tk.StringVar(value="120")
        self.invert_var = tk.BooleanVar(value=False)

        self.build_ui()

    def build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="both", expand=True)

        if not DND_AVAILABLE:
            notice = ttk.Label(
                top,
                text="Drag-and-drop is unavailable until tkinterdnd2 is installed. "
                     "Buttons still work normally.",
            )
            notice.pack(anchor="w", pady=(0, 8))

        source_box = ttk.LabelFrame(top, text="Sources", padding=8)
        source_box.pack(fill="both", expand=False)

        list_frame = ttk.Frame(source_box)
        list_frame.pack(fill="both", expand=True)

        self.source_list = tk.Listbox(list_frame, height=10)
        self.source_list.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.source_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.source_list.configure(yscrollcommand=scrollbar.set)

        if DND_AVAILABLE:
            self.source_list.drop_target_register(DND_FILES)
            self.source_list.dnd_bind("<<Drop>>", self.on_drop)

        btn_row = ttk.Frame(source_box)
        btn_row.pack(fill="x", pady=(8, 0))

        ttk.Button(btn_row, text="Add Files", command=self.add_files).pack(side="left")
        ttk.Button(btn_row, text="Add Folder", command=self.add_folder).pack(side="left", padx=(8, 0))
        ttk.Button(btn_row, text="Clear", command=self.clear_sources).pack(side="left", padx=(8, 0))

        settings = ttk.LabelFrame(top, text="Settings", padding=8)
        settings.pack(fill="x", pady=(12, 0))

        grid = ttk.Frame(settings)
        grid.pack(fill="x")

        labels = [
            ("Dither", 0, 0),
            ("Threshold", 0, 2),
            ("Fit", 1, 0),
            ("Display width", 1, 2),
            ("Display height", 1, 4),
            ("Bit order", 2, 0),
            ("Black bit", 2, 2),
            ("Video FPS", 3, 0),
            ("Max frames", 3, 2),
        ]
        for text, row, col in labels:
            ttk.Label(grid, text=text).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=4)

        ttk.Combobox(grid, textvariable=self.dither_var, values=["threshold", "bayer2", "bayer4", "floyd"], state="readonly", width=14).grid(row=0, column=1, sticky="we", pady=4)
        ttk.Entry(grid, textvariable=self.threshold_var, width=10).grid(row=0, column=3, sticky="we", pady=4)

        ttk.Combobox(grid, textvariable=self.fit_var, values=["contain", "cover", "stretch"], state="readonly", width=14).grid(row=1, column=1, sticky="we", pady=4)
        ttk.Entry(grid, textvariable=self.display_w_var, width=10).grid(row=1, column=3, sticky="we", pady=4)
        ttk.Entry(grid, textvariable=self.display_h_var, width=10).grid(row=1, column=5, sticky="we", pady=4)

        ttk.Combobox(grid, textvariable=self.bit_order_var, values=["msb", "lsb"], state="readonly", width=14).grid(row=2, column=1, sticky="we", pady=4)
        ttk.Combobox(grid, textvariable=self.black_bit_var, values=["1", "0"], state="readonly", width=14).grid(row=2, column=3, sticky="we", pady=4)

        ttk.Entry(grid, textvariable=self.video_fps_var, width=10).grid(row=3, column=1, sticky="we", pady=4)
        ttk.Entry(grid, textvariable=self.max_frames_var, width=10).grid(row=3, column=3, sticky="we", pady=4)

        ttk.Checkbutton(grid, text="Invert image", variable=self.invert_var).grid(row=3, column=5, sticky="w", padx=(0, 6), pady=4)

        for col in range(6):
            grid.columnconfigure(col, weight=1)

        action_row = ttk.Frame(top)
        action_row.pack(fill="x", pady=(12, 0))

        ttk.Button(action_row, text="Convert", command=self.convert).pack(side="left")
        ttk.Button(action_row, text="Open Output", command=self.open_output).pack(side="left", padx=(8, 0))

        log_box = ttk.LabelFrame(top, text="Log", padding=8)
        log_box.pack(fill="both", expand=True, pady=(12, 0))

        self.log = tk.Text(log_box, height=16, wrap="word")
        self.log.pack(fill="both", expand=True)

        self.append_log("SharpBit GUI ready.")
        self.append_log("Output folder: output/")
        if DND_AVAILABLE:
            self.append_log("Drag files or folders onto the source list.")
        else:
            self.append_log("Install tkinterdnd2 for drag-and-drop support.")

    def append_log(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def add_source_paths(self, paths: list[str]) -> None:
        for path_str in paths:
            path = Path(path_str).expanduser().resolve()
            if path not in self.sources:
                self.sources.append(path)
                self.source_list.insert("end", str(path))

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select files",
            filetypes=[
                ("Supported files", "*.png *.jpg *.jpeg *.bmp *.webp *.gif *.mp4 *.mov *.avi *.mkv *.webm"),
                ("All files", "*.*"),
            ],
        )
        self.add_source_paths(list(paths))

    def add_folder(self) -> None:
        path = filedialog.askdirectory(title="Select folder")
        if path:
            self.add_source_paths([path])

    def clear_sources(self) -> None:
        self.sources.clear()
        self.source_list.delete(0, "end")
        self.append_log("Sources cleared.")

    def on_drop(self, event) -> None:
        paths = split_dnd_paths(event.data)
        self.add_source_paths(paths)

    def build_overrides(self):
        return (
            {
                "dither": self.dither_var.get(),
                "threshold": int(self.threshold_var.get()),
                "fit": self.fit_var.get(),
                "max_width": int(self.display_w_var.get()),
                "max_height": int(self.display_h_var.get()),
                "bit_order": self.bit_order_var.get(),
                "black_bit": int(self.black_bit_var.get()),
                "invert_image": bool(self.invert_var.get()),
            },
            {
                "video_fps": int(self.video_fps_var.get()),
                "max_frames": int(self.max_frames_var.get()),
            },
        )

    def convert(self) -> None:
        try:
            cli_overrides, animation_overrides = self.build_overrides()
        except ValueError:
            messagebox.showerror("SharpBit", "One or more numeric fields are invalid.")
            return

        try:
            assets, animations = convert_all(
                source_items=self.sources,
                fallback_input_dir=(ROOT / "input"),
                output_dir=(ROOT / "output"),
                config_path=(ROOT / "config.json"),
                cli_overrides=cli_overrides,
                animation_cli_overrides=animation_overrides,
            )
        except RuntimeError as exc:
            messagebox.showerror("SharpBit", str(exc))
            self.append_log(f"ERROR: {exc}")
            return

        self.append_log(f"Converted static images: {len(assets)}")
        self.append_log(f"Converted animations: {len(animations)}")
        self.append_log("Done.")
        messagebox.showinfo("SharpBit", "Conversion complete.")

    def open_output(self) -> None:
        output_path = ROOT / "output"
        try:
            if sys.platform.startswith("win"):
                os.startfile(output_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(output_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(output_path)], check=False)
        except Exception as exc:
            messagebox.showerror("SharpBit", f"Cannot open output folder: {exc}")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    app = SharpBitGUI()
    app.run()
