# TextEncodingConverter

文本格式批量转换器 —— 将指定目录下的文本文件批量转换为 UTF-8 (no BOM) 编码。

## 功能

- **批量扫描**：递归搜索指定目录下所有匹配后缀的文件
- **自动编码检测**：基于 `chardet` 智能识别文件编码（GBK、GB18030、UTF-16、Big5 等）
- **安全转换**：转换为 UTF-8 (no BOM)，写入后自动验证，失败自动回滚
- **可配置后缀**：支持自定义文件后缀列表，默认 `.txt`、`.md`、`.py`
- **暂停 / 停止**：转换过程中可随时暂停、恢复或停止
- **智能并发**：文件数 ≥ 10 时自动多线程并行处理，< 10 时单线程运行
- **线程隔离**：GUI 与工作线程完全独立，界面不卡顿
- **依赖自检测**：缺少 `chardet` 时自动引导安装，不直接报错

## 环境要求

- Python 3.8+
- Windows / macOS / Linux

## 安装

```bash
pip install chardet
```

仅此一个额外依赖。Tkinter 为 Python 标准库，无需安装。

## 使用

```bash
# 直接启动（Windows 可双击）
python TextEncodingConverter.pyw

# 或直接双击 TextEncodingConverter.pyw
```

### 操作步骤

1. 点击 **浏览...** 选择需要处理的目录
2. 在右侧管理文件后缀（默认 `.txt`、`.md`、`.py`），可添加或删除
3. 点击 **转换** 开始处理
4. 转换过程中可随时 **暂停**、**恢复** 或 **停止**
5. 处理完成后弹出结果汇总对话框

## 项目结构

```
TextEncodingConverter/
├── TextEncodingConverter.pyw   # 主程序
├── CLAUDE.md                   # 项目设计文档
├── README.md                   # 本文件
└── Tests/                      # 测试用文件
    ├── 文本-ANSI.txt
    ├── 文本-GB18030.txt
    ├── 文本-UTF-16BE.txt
    ├── 文本-UTF-16LE.txt
    ├── 文本-UTF-8-BOM.txt
    └── 文本-UTF-8.txt
```

## 支持的编码

自动检测并转换以下编码：

| 编码 | 说明 |
|------|------|
| UTF-8 / UTF-8 BOM | 移除 BOM 后保留 |
| UTF-16 BE/LE | 转换为 UTF-8 |
| GBK / GB18030 / GB2312 | 中文编码，转换为 UTF-8 |
| Big5 | 繁体中文编码，转换为 UTF-8 |
| Latin-1 / ASCII | 兜底编码 |

## 许可证

MIT
