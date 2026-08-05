from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from sharpbit_core import (  # noqa: E402
    build_video_from_frames,
    convert_all,
    natural_sort_key,
    sanitize_symbol,
)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None


class SharpBitGUI:
    def __init__(self) -> None:
        self.root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
        self.root.title("SharpBit")
        self.root.geometry("820x650")
        self.root.minsize(760, 590)

        self.sources: list[Path] = []
        self.frame_sources: list[Path] = []

        self.asset_name_var = tk.StringVar()
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
        self.clean_output_var = tk.BooleanVar(value=False)

        self.rebuild_name_var = tk.StringVar()
        self.rebuild_fps_var = tk.StringVar(value="10")
        self.rebuild_format_var = tk.StringVar(value="mp4")

        self.build_ui()

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        if not DND_AVAILABLE:
            ttk.Label(
                outer,
                text=(
                    "Drag-and-drop is unavailable until tkinterdnd2 is "
                    "installed. The Add buttons still work."
                ),
            ).pack(anchor="w", pady=(0, 7))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        asset_tab = ttk.Frame(notebook, padding=10)
        video_tab = ttk.Frame(notebook, padding=10)
        notebook.add(asset_tab, text="Convert Assets")
        notebook.add(video_tab, text="Frames → Video")

        self.build_asset_tab(asset_tab)
        self.build_video_tab(video_tab)

    def build_asset_tab(self, tab: ttk.Frame) -> None:
        name_row = ttk.Frame(tab)
        name_row.pack(fill="x")
        ttk.Label(name_row, text="Asset name *").pack(side="left")
        ttk.Entry(
            name_row,
            textvariable=self.asset_name_var,
            width=32,
        ).pack(side="left", fill="x", expand=True, padx=(8, 0))
        ttk.Label(
            name_row,
            text="One source: exact name · multiple: used as prefix",
        ).pack(side="left", padx=(10, 0))

        source_box = ttk.LabelFrame(tab, text="Sources", padding=8)
        source_box.pack(fill="x", pady=(10, 0))

        list_frame = ttk.Frame(source_box)
        list_frame.pack(fill="x")
        self.source_list = tk.Listbox(list_frame, height=7)
        self.source_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.source_list.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.source_list.configure(yscrollcommand=scrollbar.set)

        if DND_AVAILABLE:
            self.source_list.drop_target_register(DND_FILES)
            self.source_list.dnd_bind("<<Drop>>", self.on_asset_drop)

        buttons = ttk.Frame(source_box)
        buttons.pack(fill="x", pady=(7, 0))
        ttk.Button(
            buttons,
            text="Add Files",
            command=self.add_asset_files,
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Add Folder",
            command=self.add_asset_folder,
        ).pack(side="left", padx=(7, 0))
        ttk.Button(
            buttons,
            text="Remove",
            command=self.remove_selected_assets,
        ).pack(side="left", padx=(7, 0))
        ttk.Button(
            buttons,
            text="Clear",
            command=self.clear_assets,
        ).pack(side="left", padx=(7, 0))

        settings = ttk.LabelFrame(tab, text="Conversion settings", padding=8)
        settings.pack(fill="x", pady=(10, 0))
        grid = ttk.Frame(settings)
        grid.pack(fill="x")

        controls = [
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
        for label, row, column in controls:
            ttk.Label(grid, text=label).grid(
                row=row,
                column=column,
                sticky="w",
                padx=(0, 5),
                pady=3,
            )

        ttk.Combobox(
            grid,
            textvariable=self.dither_var,
            values=["threshold", "bayer2", "bayer4", "floyd"],
            state="readonly",
            width=13,
        ).grid(row=0, column=1, sticky="we", pady=3)
        ttk.Entry(
            grid,
            textvariable=self.threshold_var,
            width=9,
        ).grid(row=0, column=3, sticky="we", pady=3)

        ttk.Combobox(
            grid,
            textvariable=self.fit_var,
            values=["contain", "cover", "stretch"],
            state="readonly",
            width=13,
        ).grid(row=1, column=1, sticky="we", pady=3)
        ttk.Entry(
            grid,
            textvariable=self.display_w_var,
            width=9,
        ).grid(row=1, column=3, sticky="we", pady=3)
        ttk.Entry(
            grid,
            textvariable=self.display_h_var,
            width=9,
        ).grid(row=1, column=5, sticky="we", pady=3)

        ttk.Combobox(
            grid,
            textvariable=self.bit_order_var,
            values=["msb", "lsb"],
            state="readonly",
            width=13,
        ).grid(row=2, column=1, sticky="we", pady=3)
        ttk.Combobox(
            grid,
            textvariable=self.black_bit_var,
            values=["1", "0"],
            state="readonly",
            width=13,
        ).grid(row=2, column=3, sticky="we", pady=3)

        ttk.Entry(
            grid,
            textvariable=self.video_fps_var,
            width=9,
        ).grid(row=3, column=1, sticky="we", pady=3)
        ttk.Entry(
            grid,
            textvariable=self.max_frames_var,
            width=9,
        ).grid(row=3, column=3, sticky="we", pady=3)

        ttk.Checkbutton(
            grid,
            text="Invert",
            variable=self.invert_var,
        ).grid(row=2, column=5, sticky="w", pady=3)
        ttk.Checkbutton(
            grid,
            text="Clean all previous output",
            variable=self.clean_output_var,
        ).grid(row=3, column=5, sticky="w", pady=3)

        for column in range(6):
            grid.columnconfigure(column, weight=1)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(
            actions,
            text="Convert",
            command=self.convert_assets,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Open Output",
            command=lambda: self.open_folder(ROOT / "output"),
        ).pack(side="left", padx=(7, 0))

        log_box = ttk.LabelFrame(tab, text="Log", padding=7)
        log_box.pack(fill="both", expand=True, pady=(10, 0))
        self.asset_log = tk.Text(log_box, height=9, wrap="word")
        self.asset_log.pack(fill="both", expand=True)
        self.append_asset_log("SharpBit ready.")
        self.append_asset_log(
            "Each asset is saved in its own output/generated/<name>/ folder."
        )

    def build_video_tab(self, tab: ttk.Frame) -> None:
        name_row = ttk.Frame(tab)
        name_row.pack(fill="x")
        ttk.Label(name_row, text="Video name *").pack(side="left")
        ttk.Entry(
            name_row,
            textvariable=self.rebuild_name_var,
            width=34,
        ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        frame_box = ttk.LabelFrame(tab, text="Image frames", padding=8)
        frame_box.pack(fill="both", expand=True, pady=(10, 0))

        list_frame = ttk.Frame(frame_box)
        list_frame.pack(fill="both", expand=True)
        self.frame_list = tk.Listbox(list_frame, height=15)
        self.frame_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.frame_list.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.frame_list.configure(yscrollcommand=scrollbar.set)

        if DND_AVAILABLE:
            self.frame_list.drop_target_register(DND_FILES)
            self.frame_list.dnd_bind("<<Drop>>", self.on_frame_drop)

        buttons = ttk.Frame(frame_box)
        buttons.pack(fill="x", pady=(7, 0))
        ttk.Button(
            buttons,
            text="Add Frames",
            command=self.add_frame_files,
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Add Folder",
            command=self.add_frame_folder,
        ).pack(side="left", padx=(7, 0))
        ttk.Button(
            buttons,
            text="Sort by Name",
            command=self.sort_frames,
        ).pack(side="left", padx=(7, 0))
        ttk.Button(
            buttons,
            text="Remove",
            command=self.remove_selected_frames,
        ).pack(side="left", padx=(7, 0))
        ttk.Button(
            buttons,
            text="Clear",
            command=self.clear_frames,
        ).pack(side="left", padx=(7, 0))

        settings = ttk.LabelFrame(tab, text="Video settings", padding=8)
        settings.pack(fill="x", pady=(10, 0))
        row = ttk.Frame(settings)
        row.pack(fill="x")

        ttk.Label(row, text="FPS").pack(side="left")
        ttk.Entry(
            row,
            textvariable=self.rebuild_fps_var,
            width=8,
        ).pack(side="left", padx=(7, 18))

        ttk.Label(row, text="Format").pack(side="left")
        ttk.Combobox(
            row,
            textvariable=self.rebuild_format_var,
            values=["mp4", "gif"],
            state="readonly",
            width=8,
        ).pack(side="left", padx=(7, 0))

        ttk.Label(
            row,
            text="Frames are naturally sorted: frame_2 before frame_10",
        ).pack(side="left", padx=(18, 0))

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(
            actions,
            text="Build Video",
            command=self.build_video,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Open Videos",
            command=lambda: self.open_folder(
                ROOT / "output" / "rebuilt_videos"
            ),
        ).pack(side="left", padx=(7, 0))

        log_box = ttk.LabelFrame(tab, text="Log", padding=7)
        log_box.pack(fill="x", pady=(10, 0))
        self.video_log = tk.Text(log_box, height=6, wrap="word")
        self.video_log.pack(fill="both", expand=True)
        self.append_video_log(
            "Select exported frame PNGs, choose FPS, and build MP4 or GIF."
        )

    def parse_drop_paths(self, data: str) -> list[str]:
        try:
            return list(self.root.tk.splitlist(data))
        except Exception:
            return [data.strip("{}")]

    def add_unique_paths(
        self,
        target: list[Path],
        listbox: tk.Listbox,
        paths: list[str],
    ) -> None:
        for raw in paths:
            path = Path(raw).expanduser().resolve()
            if path not in target:
                target.append(path)
        target.sort(key=natural_sort_key)
        self.refresh_listbox(target, listbox)

    @staticmethod
    def refresh_listbox(paths: list[Path], listbox: tk.Listbox) -> None:
        listbox.delete(0, "end")
        for path in paths:
            listbox.insert("end", str(path))

    @staticmethod
    def remove_selected(
        paths: list[Path],
        listbox: tk.Listbox,
    ) -> None:
        selected = list(listbox.curselection())
        for index in reversed(selected):
            del paths[index]
        SharpBitGUI.refresh_listbox(paths, listbox)

    def add_asset_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select assets",
            filetypes=[
                (
                    "Supported",
                    "*.png *.jpg *.jpeg *.bmp *.webp "
                    "*.gif *.mp4 *.mov *.avi *.mkv *.webm",
                ),
                ("All files", "*.*"),
            ],
        )
        self.add_unique_paths(
            self.sources,
            self.source_list,
            list(paths),
        )

    def add_asset_folder(self) -> None:
        path = filedialog.askdirectory(title="Select asset folder")
        if path:
            self.add_unique_paths(
                self.sources,
                self.source_list,
                [path],
            )

    def remove_selected_assets(self) -> None:
        self.remove_selected(self.sources, self.source_list)

    def clear_assets(self) -> None:
        self.sources.clear()
        self.refresh_listbox(self.sources, self.source_list)

    def on_asset_drop(self, event) -> None:
        self.add_unique_paths(
            self.sources,
            self.source_list,
            self.parse_drop_paths(event.data),
        )

    def add_frame_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select image frames",
            filetypes=[
                (
                    "Image frames",
                    "*.png *.jpg *.jpeg *.bmp *.webp",
                ),
                ("All files", "*.*"),
            ],
        )
        self.add_unique_paths(
            self.frame_sources,
            self.frame_list,
            list(paths),
        )

    def add_frame_folder(self) -> None:
        path = filedialog.askdirectory(title="Select frames folder")
        if path:
            self.add_unique_paths(
                self.frame_sources,
                self.frame_list,
                [path],
            )

    def remove_selected_frames(self) -> None:
        self.remove_selected(self.frame_sources, self.frame_list)

    def clear_frames(self) -> None:
        self.frame_sources.clear()
        self.refresh_listbox(self.frame_sources, self.frame_list)

    def sort_frames(self) -> None:
        self.frame_sources.sort(key=natural_sort_key)
        self.refresh_listbox(self.frame_sources, self.frame_list)
        self.append_video_log("Frame sources sorted by name.")

    def on_frame_drop(self, event) -> None:
        self.add_unique_paths(
            self.frame_sources,
            self.frame_list,
            self.parse_drop_paths(event.data),
        )

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

    def convert_assets(self) -> None:
        raw_name = self.asset_name_var.get().strip()
        if not raw_name:
            messagebox.showerror(
                "SharpBit",
                "Asset name is required.",
            )
            return

        try:
            effective_name = sanitize_symbol(raw_name)
            cli_overrides, animation_overrides = self.build_overrides()
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("SharpBit", str(exc))
            return

        self.set_busy(True)
        try:
            assets, animations = convert_all(
                source_items=self.sources,
                fallback_input_dir=ROOT / "input",
                output_dir=ROOT / "output",
                config_path=ROOT / "config.json",
                asset_name=effective_name,
                cli_overrides=cli_overrides,
                animation_cli_overrides=animation_overrides,
                clean_output=bool(self.clean_output_var.get()),
            )
        except RuntimeError as exc:
            messagebox.showerror("SharpBit", str(exc))
            self.append_asset_log(f"ERROR: {exc}")
            return
        finally:
            self.set_busy(False)

        names = [asset.symbol for asset in assets]
        names.extend(animation.symbol for animation in animations)
        self.append_asset_log(
            f"Converted {len(names)} asset(s): "
            + (", ".join(names) if names else "none")
        )
        messagebox.showinfo(
            "SharpBit",
            "Conversion complete.\n\n"
            "Each asset has its own .c and .h files.",
        )

    def build_video(self) -> None:
        raw_name = self.rebuild_name_var.get().strip()
        if not raw_name:
            messagebox.showerror(
                "SharpBit",
                "Video name is required.",
            )
            return
        if not self.frame_sources:
            messagebox.showerror(
                "SharpBit",
                "Select image frames or a frames folder.",
            )
            return

        try:
            fps = int(self.rebuild_fps_var.get())
            effective_name = sanitize_symbol(raw_name)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("SharpBit", str(exc))
            return

        self.set_busy(True)
        try:
            output_path = build_video_from_frames(
                frame_items=self.frame_sources,
                output_dir=ROOT / "output" / "rebuilt_videos",
                video_name=effective_name,
                fps=fps,
                output_format=self.rebuild_format_var.get(),
            )
        except RuntimeError as exc:
            messagebox.showerror("SharpBit", str(exc))
            self.append_video_log(f"ERROR: {exc}")
            return
        finally:
            self.set_busy(False)

        self.append_video_log(f"Created: {output_path}")
        messagebox.showinfo(
            "SharpBit",
            f"Video created:\n{output_path}",
        )

    def set_busy(self, busy: bool) -> None:
        self.root.configure(cursor="watch" if busy else "")
        self.root.update_idletasks()

    def append_asset_log(self, text: str) -> None:
        self.asset_log.insert("end", text + "\n")
        self.asset_log.see("end")

    def append_video_log(self, text: str) -> None:
        self.video_log.insert("end", text + "\n")
        self.video_log.see("end")

    def open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as exc:
            messagebox.showerror(
                "SharpBit",
                f"Cannot open folder: {exc}",
            )

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    SharpBitGUI().run()
