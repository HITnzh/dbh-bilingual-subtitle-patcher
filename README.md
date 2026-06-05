# DBH Bilingual Subtitle Patcher

《Detroit: Become Human》PC 版本地双语字幕补丁工具。

这个项目用于在玩家自己的游戏目录中生成并安装双语字幕：英文字幕在上，简体中文字幕在下。V1 版本已经可用于本地测试和日常游玩。

## 和 Codex 一起做的

这个项目是在 OpenAI Codex 的协助下结对开发的。人类负责方向、实机测试和最后拍板，Codex 负责把想法拧成脚本、测试和发布流程。

简单说：一个人类玩家带着一个会敲代码的搭子，把“我就想同时看懂两行字幕”这件小事认真做完。

代码、脚本、测试和 release 构建流程都放在仓库里，欢迎检查，也欢迎继续提出那些“等等，游戏里明明已经有这两种字幕”的好问题。

## V1 效果

- 字幕显示为 `English line + newline + 简体中文`
- 游戏内选择 `简体中文 / SCH` 字幕即可看到双语效果
- 使用玩家本机已有的英文和简体中文官方字幕资源生成补丁
- 自动创建备份，可用随包脚本恢复
- 不分发游戏原始文本、`.d30`、`.dat` 或任何预生成游戏资源

## 下载

请在 GitHub Releases 下载最新版本：

- [Latest release](https://github.com/HITnzh/dbh-bilingual-subtitle-patcher/releases/latest)
- V1 发布包名：`DBH-Bilingual-Subtitle-Mod-V1.zip`

发布包内包含：

- `install-v1-sch.ps1`：V1 安装脚本
- `restore-latest.ps1`：恢复最近备份
- `README_使用说明.md`：详细中文使用说明
- `NO_GAME_ASSETS.txt`：分发边界说明
- `src/`：补丁工具源码

## 使用前准备

你需要：

- Windows PowerShell 5.1 或更新版本
- Python 3.10 或更新版本
- Steam 版《Detroit: Become Human》本地游戏目录
- [`dbh-file-parser`](https://github.com/detroitbecometext/dbh-file-parser)
- [`IDX-Detroit`](https://github.com/systemsiteseason/IDX-Detroit)

本项目不会内置或重新分发这些外部工具。

## 快速安装

下载并解压 release 包后，在解压目录中打开 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\install-v1-sch.ps1 `
  -GameDir "E:\SteamLibrary\steamapps\common\Detroit Become Human" `
  -FileParser "C:\Tools\FileParser.exe" `
  -IdxDetroit "C:\Tools\IDX_Detroit.exe"
```

安装完成后启动游戏，在字幕语言中选择 `简体中文 / SCH`。

如果你的游戏目录、FileParser 或 IDX-Detroit 路径不同，请替换为自己的真实路径。完整说明见 release 包里的 `README_使用说明.md`。

## 恢复原状

安装脚本会在修改游戏文件前创建备份。需要恢复时，在解压目录运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\restore-latest.ps1 `
  -GameDir "E:\SteamLibrary\steamapps\common\Detroit Become Human"
```

恢复后建议重新打开游戏确认字幕状态。

## 安全和分发边界

这个仓库和 release 包只发布补丁工具、安装脚本和说明文档。

请不要上传或分享以下内容：

- `BigFile_PC.d30`
- `BigFile_PC.idx`
- 任何 `.dat` 游戏归档片段
- FileParser 提取出的英文/中文 JSON
- 合并后的双语字幕 JSON
- 任何包含官方游戏文本的文件

玩家应始终从自己合法安装的游戏文件中本地生成补丁。

## 免责声明

这是玩家自用工具，不是 Quantic Dream、Sony、Steam 或任何官方渠道的作品。

它会修改你本机游戏目录里的归档文件。脚本会尽量先检查、先备份、再动手，但电脑不是许愿池，Mod 也不是保险合同。使用前请关闭游戏，确认路径，保留备份；出现异常请先用 `restore-latest.ps1` 恢复，或者用 Steam 验证游戏文件。

也请不要把官方文本、提取出的字幕、生成后的双语字幕 JSON 或补丁归档打包分享。这个项目只分享工具，不搬运游戏资产。

## 开发

开发环境运行测试：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

常用本地命令：

```powershell
python -m dbh_bisub verify --game-dir "E:\SteamLibrary\steamapps\common\Detroit Become Human"
python -m dbh_bisub restore --game-dir "E:\SteamLibrary\steamapps\common\Detroit Become Human"
```

V1 发布资料位于 [`release/v1`](release/v1)。
