# DBH 双语字幕补丁 V1 使用说明

这是《Detroit: Become Human》PC 版的本地生成型双语字幕补丁工具包。V1 目标效果是：

```text
英文字幕 / 简体中文字幕
```

安装完成后，请在游戏内选择 **简体中文 / SCH** 字幕语言。

## 发布包内容

- `install-v1-sch.ps1`：一键生成并安装 V1 简体双语字幕。
- `restore-latest.ps1`：从本工具创建的备份恢复游戏文件。
- `src/`、`pyproject.toml`：本地补丁器源码。
- `NO_GAME_ASSETS.txt`：无游戏资源声明。
- `RELEASE_NOTES_V1.md`：V1 变更说明。

发布包不会包含 `BigFile_PC.d30`、`.dat`、FileParser 输出 JSON、合并后的字幕 catalog，或任何官方游戏字幕文本。

## 运行环境

需要：

- Windows PowerShell 5.1 或更新版本。
- Python 3.10 或更新版本。
- Steam 版《Detroit: Become Human》本地安装目录。
- DBH FileParser 工具。
- IDX-Detroit 工具。

辅助工具项目：

- DBH FileParser: `https://github.com/detroitbecometext/dbh-file-parser`
- IDX-Detroit: `https://github.com/systemsiteseason/IDX-Detroit`

请分别解压后记住：

- `FileParser.exe` 的完整路径。
- `IDX_Detroit.exe` 的完整路径。

## 一键安装

打开 PowerShell，进入发布包目录，然后运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\install-v1-sch.ps1 `
  -GameDir "E:\SteamLibrary\steamapps\common\Detroit Become Human" `
  -FileParser "C:\Tools\dbh-file-parser\FileParser.exe" `
  -IdxDetroit "C:\Tools\IDX-Detroit\IDX_Detroit.exe"
```

把上面的路径替换成你本机实际路径。

脚本会自动执行：

1. 检查游戏没有运行。
2. 用 FileParser 从你的本地游戏文件提取英文和简体中文字幕。
3. 合并为 `英文 / 简中` 双语字幕。
4. 用 IDX-Detroit 提取 archive `1016`。
5. 写入 `SCH` 简体中文语言块。
6. 创建安装前备份。
7. 重新打包并安装 `BigFile_PC.d30`。
8. 生成安装前后 hash 和操作报告。

默认工作目录在：

```text
%LOCALAPPDATA%\DBHBilingualSubtitlePatcher\v1-sch-时间戳
```

如果你想指定工作目录：

```powershell
.\install-v1-sch.ps1 `
  -GameDir "E:\SteamLibrary\steamapps\common\Detroit Become Human" `
  -FileParser "C:\Tools\dbh-file-parser\FileParser.exe" `
  -IdxDetroit "C:\Tools\IDX-Detroit\IDX_Detroit.exe" `
  -WorkDir "D:\DBH-Bisub-V1-Work"
```

## 游戏内设置

安装成功后启动游戏：

1. 打开游戏设置。
2. 找到字幕语言。
3. 选择 **简体中文 / SCH**。
4. 保持字幕开启。

如果选择 **繁体中文 / CHT**，看到的可能仍是繁体双语或繁体字幕，这不是 V1 推荐路线。

## 回滚 / 卸载

安装脚本会在游戏目录下创建：

```text
.dbh-bisub-backups\时间戳
```

恢复最新备份：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\restore-latest.ps1 `
  -GameDir "E:\SteamLibrary\steamapps\common\Detroit Become Human"
```

恢复指定备份：

```powershell
.\restore-latest.ps1 `
  -GameDir "E:\SteamLibrary\steamapps\common\Detroit Become Human" `
  -BackupId "20260605T042041Z"
```

如果没有可用备份，也可以在 Steam 中执行“验证游戏文件完整性”恢复原始文件。

## 常见问题

### 仍然看到繁体中文

请确认游戏里选择的是 **简体中文 / SCH**，不是 **繁体中文 / CHT**。

### PowerShell 不允许运行脚本

只对当前 PowerShell 窗口临时放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 安装脚本提示游戏正在运行

关闭游戏和相关进程后再运行。补丁需要写入 `BigFile_PC.idx` 和 `BigFile_PC.d30`。

### 安装失败后怎么办

先看脚本输出的 `Reports` 目录。每一步都有 JSON 或日志文件。通常失败原因是：

- 工具路径填错。
- 游戏目录填错。
- 工作目录复用了旧内容。
- 游戏正在运行。

如果已经写入过游戏文件，运行 `restore-latest.ps1` 回滚。

## 发布与分发边界

可以分发这个 V1 工具包。

不要分发：

- 生成后的 `BigFile_PC.d30`。
- IDX 解包出的 `.dat` / `.txt`。
- FileParser 输出的 `eng.json`、`sch.json`、`chi.json`。
- 合并后的 `bilingual*.json`。

这些文件包含官方游戏资源或官方字幕文本，应由用户在自己的电脑上本地生成。
