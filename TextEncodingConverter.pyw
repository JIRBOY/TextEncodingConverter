"""
文本格式批量转换器
批量将文本文件从任意编码转换为 UTF-8 (no BOM)
"""

import os
import sys
import io
import glob
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# 依赖检查
# ============================================================

def ensure_chardet():
    """确保 chardet 已安装，未安装时自动尝试 pip install"""
    try:
        import chardet
        return True
    except ImportError:
        pass

    # 尝试自动安装
    result = messagebox.askyesno(
        "缺少依赖",
        "需要安装 'chardet' 库用于编码检测。\n"
        "是否现在自动安装？"
    )
    if not result:
        return False

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "chardet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        messagebox.showinfo("安装成功", "'chardet' 已安装，程序将继续运行。")
        return True
    except Exception as e:
        messagebox.showerror(
            "安装失败",
            f"自动安装 'chardet' 失败，请手动运行：\n"
            f"pip install chardet\n\n"
            f"错误信息：{e}"
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
    转换单个文件。
    返回 (file_path, success, message)
    """
    # 检查停止
    if stop_event.is_set():
        return file_path, False, "已停止"

    # 等待暂停
    pause_event.wait()

    filename = os.path.basename(file_path)
    log_queue.put(("info", f"处理: {filename}"))

    try:
        # 1. 读取原始字节
        with open(file_path, "rb") as f:
            raw = f.read()

        if len(raw) == 0:
            log_queue.put(("info", f"  {filename}: 空文件，跳过"))
            return file_path, True, "空文件"

        # 2. 检测编码
        detected_encoding, _ = detect_encoding(file_path)
        log_queue.put(("info", f"  检测编码: {detected_encoding}"))

        # 3. 尝试解码原始内容
        text = None
        used_encoding = None

        # 优先使用 chardet 结果
        if detected_encoding:
            success, text = try_decode(raw, detected_encoding)
            if success and not is_garbled(text):
                used_encoding = detected_encoding

        # 如果 chardet 结果不可靠，遍历候选编码
        if text is None:
            for enc in CANDIDATE_ENCODINGS:
                success, text = try_decode(raw, enc)
                if success and not is_garbled(text):
                    used_encoding = enc
                    break

        if text is None:
            # 最后尝试 latin-1（永不失败）
            text = raw.decode("latin-1")
            used_encoding = "latin-1"
            log_queue.put(("warn", f"  所有编码尝试失败，使用 latin-1 兜底"))

        log_queue.put(("info", f"  使用编码: {used_encoding}"))

        # 4. 如果已经是 UTF-8 无 BOM，检查是否需要转换
        if used_encoding in ("utf-8",):
            # 检查是否有 BOM
            if raw.startswith(b"\xef\xbb\xbf"):
                log_queue.put(("info", f"  检测到 UTF-8 BOM，移除 BOM"))
            else:
                log_queue.put(("info", f"  已经是 UTF-8 (no BOM)，跳过"))
                return file_path, True, "已是 UTF-8"

        # 5. 写回 UTF-8 (no BOM)
        # 备份内容到内存（用于回滚）
        original_raw = raw

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
        except IOError as e:
            log_queue.put(("error", f"  写入失败: {e}"))
            return file_path, False, f"写入失败: {e}"

        # 6. 验证：重新读取
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                verify_text = f.read()
            if is_garbled(verify_text):
                raise ValueError("验证时发现乱码")
            if verify_text != text:
                raise ValueError("验证时内容不一致")
        except Exception as e:
            # 回滚
            log_queue.put(("warn", f"  验证失败，回滚原始内容: {e}"))
            try:
                with open(file_path, "wb") as f:
                    f.write(original_raw)
            except IOError:
                pass
            return file_path, False, f"验证失败，已回滚: {e}"

        log_queue.put(("info", f"  {filename}: 转换成功 -> UTF-8 (no BOM)"))
        return file_path, True, "成功"

    except Exception as e:
        log_queue.put(("error", f"  {filename}: 处理异常: {e}"))
        return file_path, False, str(e)


# ============================================================
# 文件扫描
# ============================================================

def scan_files(directory, extensions):
    """递归扫描目录下指定后缀的文件"""
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
    """文件转换控制器，管理线程与状态"""

    def __init__(self, log_queue):
        self.log_queue = log_queue
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # 初始为非暂停状态
        self.worker_thread = None
        self.is_running = False

    def start(self, directory, extensions):
        """启动转换线程"""
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
        """暂停转换"""
        self.pause_event.clear()

    def resume(self):
        """恢复转换"""
        self.pause_event.set()

    def stop(self):
        """停止转换"""
        self.stop_event.set()
        self.pause_event.set()  # 确保不被阻塞

    def _run(self, directory, extensions):
        """工作线程入口"""
        self.log_queue.put(("info", f"扫描目录: {directory}"))

        files = scan_files(directory, extensions)
        total = len(files)

        if total == 0:
            self.log_queue.put(("warn", "未找到匹配的文件"))
            self.log_queue.put(("done", 0, 0, 0))
            self.is_running = False
            return

        self.log_queue.put(("info", f"找到 {total} 个文件"))

        success_count = 0
        fail_count = 0
        skip_count = 0

        # 并发策略
        use_threads = total >= 10
        max_workers = min(total, 4) if use_threads else 1

        self.log_queue.put(("info", f"{'并行' if use_threads else '单线程'} 处理中..."))

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
                    fp, success, msg = future.result()
                    if success:
                        if msg == "已是 UTF-8" or msg == "空文件":
                            skip_count += 1
                        else:
                            success_count += 1
                    else:
                        fail_count += 1
        else:
            # 单线程
            for fp in files:
                if self.stop_event.is_set():
                    break
                # 暂停等待
                self.pause_event.wait()

                fp, success, msg = convert_single_file(
                    fp, self.log_queue,
                    self.stop_event, self.pause_event,
                )
                if success:
                    if msg == "已是 UTF-8" or msg == "空文件":
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
    """主窗口"""

    def __init__(self, root):
        self.root = root
        self.root.title("文本格式批量转换器")
        self.root.geometry("600x520")
        self.root.resizable(True, True)
        # 居中显示
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
        # ---- 路径选择 ----
        path_frame = ttk.Frame(self.root, padding=(10, 10, 10, 5))
        path_frame.pack(fill=tk.X)

        ttk.Label(path_frame, text="处理路径:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Button(path_frame, text="浏览...", command=self._browse).pack(side=tk.LEFT)

        # ---- 后缀管理 ----
        ext_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        ext_frame.pack(fill=tk.X)

        ttk.Label(ext_frame, text="文件后缀:").pack(side=tk.LEFT)

        self.ext_listbox = tk.Listbox(ext_frame, height=3, selectmode=tk.SINGLE)
        self.ext_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        # 默认后缀
        for ext in [".txt", ".md", ".py"]:
            self.ext_listbox.insert(tk.END, ext)

        ext_btn_frame = ttk.Frame(ext_frame)
        ext_btn_frame.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Button(ext_btn_frame, text="添加", command=self._add_ext).pack(fill=tk.X)
        ttk.Button(ext_btn_frame, text="删除", command=self._remove_ext).pack(fill=tk.X)

        # ---- 日志区域 ----
        log_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        log_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(log_frame, text="处理日志:").pack(anchor=tk.W)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_container, height=12, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- 进度条 ----
        progress_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        progress_frame.pack(fill=tk.X)

        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(fill=tk.X)

        self.progress_label = ttk.Label(progress_frame, text="就绪", foreground="gray")
        self.progress_label.pack(anchor=tk.W)

        # ---- 控制按钮 ----
        btn_frame = ttk.Frame(self.root, padding=(10, 5, 10, 10))
        btn_frame.pack(fill=tk.X)

        self.btn_convert = ttk.Button(btn_frame, text="转换", command=self._convert)
        self.btn_convert.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_pause = ttk.Button(btn_frame, text="暂停", command=self._pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_stop = ttk.Button(btn_frame, text="停止", command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Separator(btn_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self.btn_exit = ttk.Button(btn_frame, text="退出", command=self._exit)
        self.btn_exit.pack(side=tk.RIGHT)

    def _browse(self):
        directory = filedialog.askdirectory(title="选择处理路径")
        if directory:
            self.path_var.set(directory)

    def _add_ext(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("添加后缀")
        dialog.geometry("300x100")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="输入后缀（如 .json）:").pack(pady=(10, 5))
        entry = ttk.Entry(dialog, width=30)
        entry.pack()

        def confirm():
            val = entry.get().strip().lower()
            if not val.startswith("."):
                val = "." + val
            if val and val not in self._get_extensions():
                self.ext_listbox.insert(tk.END, val)
            dialog.destroy()

        ttk.Button(dialog, text="确定", command=confirm).pack(pady=5)

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
        """处理来自工作线程的消息"""
        msg_type = msg[0]
        if msg_type == "info":
            self._log(msg[1], "info")
        elif msg_type == "warn":
            self._log(msg[1], "warn")
        elif msg_type == "error":
            self._log(msg[1], "error")
        elif msg_type == "done":
            # (processed, success, fail, skip)
            processed = msg[1]
            success = msg[2]
            fail = msg[3]
            skip = msg[4] if len(msg) > 4 else 0

            self.progress["value"] = 100
            self.progress_label["text"] = f"完成：处理 {processed} 个，成功 {success} 个"

            if fail > 0:
                self.progress_label["text"] += f"，失败 {fail} 个"

            if skip > 0:
                self.progress_label["text"] += f"，跳过 {skip} 个"

            btn_state = tk.NORMAL if fail == 0 else tk.NORMAL
            self._set_buttons_idle()

            # 弹出完成对话框
            result_msg = (
                f"处理完成！\n\n"
                f"共处理: {processed} 个文件\n"
                f"转换成功: {success} 个\n"
                f"跳过（已是 UTF-8）: {skip} 个\n"
                f"失败: {fail} 个"
            )
            if fail > 0:
                messagebox.showwarning("处理完成（有失败）", result_msg)
            else:
                messagebox.showinfo("处理完成", result_msg)

    def _convert(self):
        """点击转换按钮"""
        directory = self.path_var.get().strip()
        if not directory or not os.path.isdir(directory):
            messagebox.showerror("错误", "请选择有效的处理路径")
            return

        extensions = self._get_extensions()
        if not extensions:
            messagebox.showerror("错误", "请至少添加一个文件后缀")
            return

        # 清空日志
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self.progress["value"] = 0
        self.progress_label["text"] = "正在扫描..."

        self._set_buttons_running()
        self.controller.start(directory, extensions)

    def _pause(self):
        """点击暂停/恢复按钮"""
        if self.controller.pause_event.is_set():
            self.controller.pause()
            self.btn_pause["text"] = "恢复"
            self._log("已暂停", "warn")
        else:
            self.controller.resume()
            self.btn_pause["text"] = "暂停"
            self._log("已恢复", "info")

    def _stop(self):
        """点击停止按钮"""
        self._log("正在停止...", "warn")
        self.controller.stop()

    def _exit(self):
        """退出程序"""
        if self.controller.is_running:
            result = messagebox.askyesno(
                "确认退出",
                "转换正在进行中，确定要退出吗？\n"
                "未完成的文件将被停止。"
            )
            if not result:
                return
            # 清理工作线程
            self.controller.stop()
            self._log("正在清理...", "warn")

        self.root.destroy()

    def _set_buttons_running(self):
        self.btn_convert["state"] = tk.DISABLED
        self.btn_pause["state"] = tk.NORMAL
        self.btn_stop["state"] = tk.NORMAL

    def _set_buttons_idle(self):
        self.btn_convert["state"] = tk.NORMAL
        self.btn_pause["state"] = tk.DISABLED
        self.btn_pause["text"] = "暂停"
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
