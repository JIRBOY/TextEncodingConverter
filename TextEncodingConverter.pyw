"""
Text Encoding Batch Converter
Batch converts text files from any encoding to UTF-8 (no BOM)
"""

import os
import sys
import io
import glob
import queue
import shutil
import subprocess
import locale
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# i18n - Internationalization
# ============================================================

class I18n:
    """Simple i18n system based on system locale."""

    TRANSLATIONS = {
        "en": {
            # Window
            "app_title": "Text Encoding Converter",
            # Labels
            "path_label": "Path:",
            "browse": "Browse...",
            "ext_label": "Extensions:",
            "add": "Add",
            "remove": "Remove",
            "log_label": "Log:",
            # Buttons
            "convert": "Convert",
            "pause": "Pause",
            "resume": "Resume",
            "stop": "Stop",
            "exit": "Exit",
            # Dialogs
            "select_path": "Select Processing Path",
            "add_ext_title": "Add Extension",
            "add_ext_label": "Enter extension (e.g. .json):",
            "confirm": "OK",
            "error": "Error",
            "no_path": "Please select a valid processing path.",
            "no_ext": "Please add at least one file extension.",
            "exit_confirm": "Confirm Exit",
            "exit_msg": "Conversion is in progress. Are you sure you want to exit?\nUnfinished files will be stopped.",
            # Completion
            "done_title": "Processing Complete",
            "done_title_warn": "Processing Complete (with errors)",
            "done_msg": "Processing complete!\n\n"
                       "Files processed: {processed}\n"
                       "Converted successfully: {success}\n"
                       "Skipped (already UTF-8): {skip}\n"
                       "Failed: {fail}",
            # Dependency
            "dep_missing": "Missing Dependency",
            "dep_msg": "The 'chardet' library is required for encoding detection.\nInstall it now?",
            "dep_ok": "Installation Successful",
            "dep_ok_msg": "'chardet' has been installed. The program will now continue.",
            "dep_fail": "Installation Failed",
            "dep_fail_msg": "Failed to auto-install 'chardet'. Please run manually:\n"
                           "pip install chardet\n\nError: {error}",
            # Status
            "ready": "Ready",
            "scanning": "Scanning...",
            "processing_parallel": "Processing (parallel)...",
            "processing_single": "Processing (single thread)...",
            # Log messages
            "log_scanning": "Scanning directory: {dir}",
            "log_no_files": "No matching files found.",
            "log_found": "Found {count} files",
            "log_processing": "Processing: {file}",
            "log_empty": "  {file}: Empty file, skipped",
            "log_detect": "  Detected encoding: {enc}",
            "log_use": "  Using encoding: {enc}",
            "log_bom": "  UTF-8 BOM detected, removing BOM",
            "log_utf8": "  Already UTF-8 (no BOM), skipped",
            "log_write_fail": "  Write failed: {err}",
            "log_verify_fail": "  Verification failed, rolling back: {err}",
            "log_fallback": "  All encoding attempts failed, falling back to latin-1",
            "log_success": "  {file}: Converted -> UTF-8 (no BOM)",
            "log_error": "  {file}: Processing error: {err}",
            "log_paused": "Paused",
            "log_resuming": "Resumed",
            "log_stopping": "Stopping...",
            "log_cleaning": "Cleaning up...",
            "log_done": "Done: processed {processed}, success {success}",
            "log_done_fail": ", failed {fail}",
            "log_done_skip": ", skipped {skip}",
            # Conversion results
            "res_stopped": "Stopped",
            "res_empty": "Empty file",
            "res_utf8": "Already UTF-8",
            "res_success": "Success",
            "res_write_fail": "Write failed: {err}",
            "res_verify_fail": "Verification failed, rolled back: {err}",
        },
        "zh": {
            # Window
            "app_title": "文本格式批量转换器",
            # Labels
            "path_label": "处理路径:",
            "browse": "浏览...",
            "ext_label": "文件后缀:",
            "add": "添加",
            "remove": "删除",
            "log_label": "处理日志:",
            # Buttons
            "convert": "转换",
            "pause": "暂停",
            "resume": "恢复",
            "stop": "停止",
            "exit": "退出",
            # Dialogs
            "select_path": "选择处理路径",
            "add_ext_title": "添加后缀",
            "add_ext_label": "输入后缀（如 .json）:",
            "confirm": "确定",
            "error": "错误",
            "no_path": "请选择有效的处理路径",
            "no_ext": "请至少添加一个文件后缀",
            "exit_confirm": "确认退出",
            "exit_msg": "转换正在进行中，确定要退出吗？\n未完成的文件将被停止。",
            # Completion
            "done_title": "处理完成",
            "done_title_warn": "处理完成（有失败）",
            "done_msg": "处理完成！\n\n"
                       "共处理: {processed} 个文件\n"
                       "转换成功: {success} 个\n"
                       "跳过（已是 UTF-8）: {skip} 个\n"
                       "失败: {fail} 个",
            # Dependency
            "dep_missing": "缺少依赖",
            "dep_msg": "需要安装 'chardet' 库用于编码检测。\n是否现在自动安装？",
            "dep_ok": "安装成功",
            "dep_ok_msg": "'chardet' 已安装，程序将继续运行。",
            "dep_fail": "安装失败",
            "dep_fail_msg": "自动安装 'chardet' 失败，请手动运行：\n"
                           "pip install chardet\n\n"
                           "错误信息：{error}",
            # Status
            "ready": "就绪",
            "scanning": "正在扫描...",
            "processing_parallel": "并行处理中...",
            "processing_single": "单线程处理中...",
            # Log messages
            "log_scanning": "扫描目录: {dir}",
            "log_no_files": "未找到匹配的文件",
            "log_found": "找到 {count} 个文件",
            "log_processing": "处理: {file}",
            "log_empty": "  {file}: 空文件，跳过",
            "log_detect": "  检测编码: {enc}",
            "log_use": "  使用编码: {enc}",
            "log_bom": "  检测到 UTF-8 BOM，移除 BOM",
            "log_utf8": "  已经是 UTF-8 (no BOM)，跳过",
            "log_write_fail": "  写入失败: {err}",
            "log_verify_fail": "  验证失败，回滚原始内容: {err}",
            "log_fallback": "  所有编码尝试失败，使用 latin-1 兜底",
            "log_success": "  {file}: 转换成功 -> UTF-8 (no BOM)",
            "log_error": "  {file}: 处理异常: {err}",
            "log_paused": "已暂停",
            "log_resuming": "已恢复",
            "log_stopping": "正在停止...",
            "log_cleaning": "正在清理...",
            "log_done": "完成：处理 {processed} 个，成功 {success} 个",
            "log_done_fail": "，失败 {fail} 个",
            "log_done_skip": "，跳过 {skip} 个",
            # Conversion results
            "res_stopped": "已停止",
            "res_empty": "空文件",
            "res_utf8": "已是 UTF-8",
            "res_success": "成功",
            "res_write_fail": "写入失败: {err}",
            "res_verify_fail": "验证失败，已回滚: {err}",
        },
    }

    def __init__(self):
        self.lang = self._detect_language()

    @staticmethod
    def _detect_language():
        """Detect system language. Returns 'zh' for Chinese, 'en' for others."""
        try:
            lang_tag = locale.getdefaultlocale()[0] or ""
            lang_tag = lang_tag.lower()
        except Exception:
            lang_tag = ""

        if "zh" in lang_tag:
            return "zh"
        return "en"

    def __call__(self, key, **kwargs):
        """Allow using _() as a shorthand for _.t()."""
        return self.t(key, **kwargs)

    def t(self, key, **kwargs):
        """Translate a key. Supports {placeholder} formatting."""
        text = self.TRANSLATIONS.get(self.lang, {}).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text


# Global i18n instance
_ = I18n()


# ============================================================
# 依赖检查
# ============================================================

def ensure_chardet():
    """Ensure chardet is installed, auto-install if needed."""
    try:
        import chardet
        return True
    except ImportError:
        pass

    result = messagebox.askyesno(
        _("dep_missing"),
        _("dep_msg")
    )
    if not result:
        return False

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "chardet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        messagebox.showinfo(_("dep_ok"), _("dep_ok_msg"))
        return True
    except Exception as e:
        messagebox.showerror(
            _("dep_fail"),
            _("dep_fail_msg", error=str(e))
        )
        return False


# ============================================================
# 编码检测与转换
# ============================================================

# 候选编码列表（从严格到宽松）
CANDIDATE_ENCODINGS = [
    "utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be",
    "gb18030", "gbk", "gb2312", "big5",
    "latin-1", "ascii",
]


def detect_encoding(file_path):
    """使用 chardet 检测文件编码"""
    import chardet
    with open(file_path, "rb") as f:
        raw = f.read()
    if len(raw) == 0:
        return "utf-8", raw
    result = chardet.detect(raw)
    encoding = result.get("encoding", None)
    if encoding:
        encoding = encoding.lower()
    # chardet 可能返回 None 或不可靠结果，做一下映射
    if encoding in ("gb2312", "gb2312", "hz_gb_2312"):
        encoding = "gb18030"  # GB18030 是 GB2312 的超集，更安全
    if encoding in ("iso-8859-1",):
        encoding = "latin-1"
    return encoding, raw


def try_decode(raw, encoding):
    """尝试用指定编码解码字节，返回 (success, text)"""
    try:
        text = raw.decode(encoding)
        return True, text
    except (UnicodeDecodeError, LookupError):
        return False, None


def is_garbled(text):
    """启发式判断文本是否为乱码"""
    if not text:
        return True
    # 替换字符比例过高
    replacement_count = text.count("\ufffd")
    if replacement_count > len(text) * 0.05:
        return True
    # 不可打印字符比例过高（排除换行和制表符）
    non_printable = sum(1 for c in text if not c.isprintable() and c not in ("\n", "\r", "\t"))
    if non_printable > len(text) * 0.1:
        return True
    return False


def convert_single_file(file_path, log_queue, stop_event, pause_event):
    """
    Convert a single file.
    Returns (file_path, success, message_key, message_kwargs)
    """
    if stop_event.is_set():
        return file_path, False, "res_stopped", {}

    pause_event.wait()

    filename = os.path.basename(file_path)
    log_queue.put(("info", _("log_processing", file=filename)))

    try:
        with open(file_path, "rb") as f:
            raw = f.read()

        if len(raw) == 0:
            log_queue.put(("info", _("log_empty", file=filename)))
            return file_path, True, "res_empty", {}

        detected_encoding, raw_data = detect_encoding(file_path)
        log_queue.put(("info", _("log_detect", enc=detected_encoding)))

        text = None
        used_encoding = None

        if detected_encoding:
            success, text = try_decode(raw, detected_encoding)
            if success and not is_garbled(text):
                used_encoding = detected_encoding

        if text is None:
            for enc in CANDIDATE_ENCODINGS:
                success, text = try_decode(raw, enc)
                if success and not is_garbled(text):
                    used_encoding = enc
                    break

        if text is None:
            text = raw.decode("latin-1")
            used_encoding = "latin-1"
            log_queue.put(("warn", _("log_fallback")))

        log_queue.put(("info", _("log_use", enc=used_encoding)))

        if used_encoding in ("utf-8",):
            if raw.startswith(b"\xef\xbb\xbf"):
                log_queue.put(("info", _("log_bom")))
            else:
                log_queue.put(("info", _("log_utf8")))
                return file_path, True, "res_utf8", {}

        original_raw = raw

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
        except IOError as e:
            log_queue.put(("error", _("log_write_fail", err=str(e))))
            return file_path, False, "res_write_fail", {"err": str(e)}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                verify_text = f.read()
            if is_garbled(verify_text):
                raise ValueError("Garbled text on verify")
            if verify_text != text:
                raise ValueError("Content mismatch on verify")
        except Exception as e:
            log_queue.put(("warn", _("log_verify_fail", err=str(e))))
            try:
                with open(file_path, "wb") as f:
                    f.write(original_raw)
            except IOError:
                pass
            return file_path, False, "res_verify_fail", {"err": str(e)}

        log_queue.put(("info", _("log_success", file=filename)))
        return file_path, True, "res_success", {}

    except Exception as e:
        log_queue.put(("error", _("log_error", file=filename, err=str(e))))
        return file_path, False, "res_error", {"err": str(e)}


# ============================================================
# 文件扫描
# ============================================================

def scan_files(directory, extensions):
    """Recursively scan directory for files with given extensions."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in extensions:
                files.append(os.path.join(root, fn))
    return files


# ============================================================
# 控制器
# ============================================================

class ConverterController:
    """File conversion controller, manages threads and state."""

    def __init__(self, log_queue):
        self.log_queue = log_queue
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.worker_thread = None
        self.is_running = False

    def start(self, directory, extensions):
        """Start conversion thread."""
        if self.is_running:
            return
        self.stop_event.clear()
        self.pause_event.set()
        self.is_running = True
        self.worker_thread = threading.Thread(
            target=self._run,
            args=(directory, extensions),
            daemon=True,
        )
        self.worker_thread.start()

    def pause(self):
        """Pause conversion."""
        self.pause_event.clear()

    def resume(self):
        """Resume conversion."""
        self.pause_event.set()

    def stop(self):
        """Stop conversion."""
        self.stop_event.set()
        self.pause_event.set()

    def _run(self, directory, extensions):
        """Worker thread entry point."""
        self.log_queue.put(("info", _("log_scanning", dir=directory)))

        files = scan_files(directory, extensions)
        total = len(files)

        if total == 0:
            self.log_queue.put(("warn", _("log_no_files")))
            self.log_queue.put(("done", 0, 0, 0))
            self.is_running = False
            return

        self.log_queue.put(("info", _("log_found", count=total)))

        success_count = 0
        fail_count = 0
        skip_count = 0

        use_threads = total >= 10
        max_workers = min(total, 4) if use_threads else 1

        mode_key = "processing_parallel" if use_threads else "processing_single"
        self.log_queue.put(("info", _(mode_key)))

        if use_threads:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for fp in files:
                    if self.stop_event.is_set():
                        break
                    future = executor.submit(
                        convert_single_file,
                        fp, self.log_queue,
                        self.stop_event, self.pause_event,
                    )
                    futures[future] = fp

                for future in as_completed(futures):
                    if self.stop_event.is_set():
                        break
                    fp, success, msg_key, msg_kwargs = future.result()
                    if success:
                        if msg_key in ("res_utf8", "res_empty"):
                            skip_count += 1
                        else:
                            success_count += 1
                    else:
                        fail_count += 1
        else:
            for fp in files:
                if self.stop_event.is_set():
                    break
                self.pause_event.wait()

                fp, success, msg_key, msg_kwargs = convert_single_file(
                    fp, self.log_queue,
                    self.stop_event, self.pause_event,
                )
                if success:
                    if msg_key in ("res_utf8", "res_empty"):
                        skip_count += 1
                    else:
                        success_count += 1
                else:
                    fail_count += 1

        processed = success_count + fail_count
        self.log_queue.put(
            ("done", processed, success_count, fail_count, skip_count)
        )
        self.is_running = False


# ============================================================
# GUI
# ============================================================

class MainWindow:
    """Main application window."""

    def __init__(self, root):
        self.root = root
        self.root.title(_("app_title"))
        self.root.geometry("600x520")
        self.root.resizable(True, True)
        self._center_window(600, 520)

        self.log_queue = queue.Queue()
        self.controller = ConverterController(self.log_queue)

        self._build_ui()
        self._start_queue_poller()

    def _center_window(self, w, h):
        """窗口居中"""
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = (ws - w) // 2
        y = (hs - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # ---- Path selection ----
        path_frame = ttk.Frame(self.root, padding=(10, 10, 10, 5))
        path_frame.pack(fill=tk.X)

        ttk.Label(path_frame, text=_("path_label")).pack(side=tk.LEFT)
        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Button(path_frame, text=_("browse"), command=self._browse).pack(side=tk.LEFT)

        # ---- Extension management ----
        ext_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        ext_frame.pack(fill=tk.X)

        ttk.Label(ext_frame, text=_("ext_label")).pack(side=tk.LEFT)

        self.ext_listbox = tk.Listbox(ext_frame, height=3, selectmode=tk.SINGLE)
        self.ext_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        for ext in [".txt", ".md", ".py"]:
            self.ext_listbox.insert(tk.END, ext)

        ext_btn_frame = ttk.Frame(ext_frame)
        ext_btn_frame.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Button(ext_btn_frame, text=_("add"), command=self._add_ext).pack(fill=tk.X)
        ttk.Button(ext_btn_frame, text=_("remove"), command=self._remove_ext).pack(fill=tk.X)

        # ---- Log area ----
        log_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        log_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(log_frame, text=_("log_label")).pack(anchor=tk.W)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_container, height=12, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Progress bar ----
        progress_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        progress_frame.pack(fill=tk.X)

        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(fill=tk.X)

        self.progress_label = ttk.Label(progress_frame, text=_("ready"), foreground="gray")
        self.progress_label.pack(anchor=tk.W)

        # ---- Control buttons ----
        btn_frame = ttk.Frame(self.root, padding=(10, 5, 10, 10))
        btn_frame.pack(fill=tk.X)

        self.btn_convert = ttk.Button(btn_frame, text=_("convert"), command=self._convert)
        self.btn_convert.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_pause = ttk.Button(btn_frame, text=_("pause"), command=self._pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_stop = ttk.Button(btn_frame, text=_("stop"), command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self.btn_exit = ttk.Button(btn_frame, text=_("exit"), command=self._exit)
        self.btn_exit.pack(side=tk.RIGHT)

    def _browse(self):
        directory = filedialog.askdirectory(title=_("select_path"))
        if directory:
            self.path_var.set(directory)

    def _add_ext(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(_("add_ext_title"))
        dialog.geometry("300x100")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_("add_ext_label")).pack(pady=(10, 5))
        entry = ttk.Entry(dialog, width=30)
        entry.pack()

        def confirm():
            val = entry.get().strip().lower()
            if not val.startswith("."):
                val = "." + val
            if val and val not in self._get_extensions():
                self.ext_listbox.insert(tk.END, val)
            dialog.destroy()

        ttk.Button(dialog, text=_("confirm"), command=confirm).pack(pady=5)

    def _remove_ext(self):
        sel = self.ext_listbox.curselection()
        if sel:
            self.ext_listbox.delete(sel[0])

    def _get_extensions(self):
        return [self.ext_listbox.get(i) for i in range(self.ext_listbox.size())]

    def _log(self, msg, level="info"):
        """添加日志到文本框"""
        self.log_text.configure(state=tk.NORMAL)
        colors = {
            "info": "black",
            "warn": "#CC6600",
            "error": "red",
            "success": "green",
        }
        color = colors.get(level, "black")
        self.log_text.insert(tk.END, msg + "\n", color)
        self.log_text.tag_config(color, foreground=color)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _start_queue_poller(self):
        """定期检查队列，更新UI"""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._handle_queue_msg(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._start_queue_poller)

    def _handle_queue_msg(self, msg):
        """Handle messages from worker thread."""
        msg_type = msg[0]
        if msg_type == "info":
            self._log(msg[1], "info")
        elif msg_type == "warn":
            self._log(msg[1], "warn")
        elif msg_type == "error":
            self._log(msg[1], "error")
        elif msg_type == "done":
            processed = msg[1]
            success = msg[2]
            fail = msg[3]
            skip = msg[4] if len(msg) > 4 else 0

            self.progress["value"] = 100
            status_text = _("log_done", processed=processed, success=success)
            if fail > 0:
                status_text += _("log_done_fail", fail=fail)
            if skip > 0:
                status_text += _("log_done_skip", skip=skip)
            self.progress_label["text"] = status_text

            self._set_buttons_idle()

            result_msg = _("done_msg",
                           processed=processed, success=success,
                           skip=skip, fail=fail)
            if fail > 0:
                messagebox.showwarning(_("done_title_warn"), result_msg)
            else:
                messagebox.showinfo(_("done_title"), result_msg)

    def _convert(self):
        """Convert button clicked."""
        directory = self.path_var.get().strip()
        if not directory or not os.path.isdir(directory):
            messagebox.showerror(_("error"), _("no_path"))
            return

        extensions = self._get_extensions()
        if not extensions:
            messagebox.showerror(_("error"), _("no_ext"))
            return

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self.progress["value"] = 0
        self.progress_label["text"] = _("scanning")

        self._set_buttons_running()
        self.controller.start(directory, extensions)

    def _pause(self):
        """Pause/Resume button clicked."""
        if self.controller.pause_event.is_set():
            self.controller.pause()
            self.btn_pause["text"] = _("resume")
            self._log(_("log_paused"), "warn")
        else:
            self.controller.resume()
            self.btn_pause["text"] = _("pause")
            self._log(_("log_resuming"), "info")

    def _stop(self):
        """Stop button clicked."""
        self._log(_("log_stopping"), "warn")
        self.controller.stop()

    def _exit(self):
        """Exit application."""
        if self.controller.is_running:
            result = messagebox.askyesno(
                _("exit_confirm"),
                _("exit_msg")
            )
            if not result:
                return
            self.controller.stop()
            self._log(_("log_cleaning"), "warn")

        self.root.destroy()

    def _set_buttons_running(self):
        self.btn_convert["state"] = tk.DISABLED
        self.btn_pause["state"] = tk.NORMAL
        self.btn_stop["state"] = tk.NORMAL

    def _set_buttons_idle(self):
        self.btn_convert["state"] = tk.NORMAL
        self.btn_pause["state"] = tk.DISABLED
        self.btn_pause["text"] = _("pause")
        self.btn_stop["state"] = tk.DISABLED


# ============================================================
# 入口
# ============================================================

def main():
    if not ensure_chardet():
        sys.exit(1)

    root = tk.Tk()
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
