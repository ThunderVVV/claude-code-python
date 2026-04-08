# 开发过程AI使用记录

## 总结

1. GPT5.4 >> GLM-5 > doubao-seed-code-2.0
2. 大部分问题集中在前端，GLM-5的前端解决问题的能力非常不足，有相当多的问题即使battle很多轮也白搭，给再多的提示模型也根本解决不了。
3. doubao解决前端问题的能力也很差，给了三个前端问题，一个问题都没解决
4. GPT-5.4也不能一下解决所有前端问题，有些细粒度问题需要多轮人工测试和引导。即使对于最顶级的模型，前端仍然是道阻且长，前端场景下多模态细粒度感知能力感觉未来会非常重要

## 万恶之源：突发奇想让AI用python重写claude code

## Opencode doubao-seed-code-2.0

这个是claude code 的typescritpt源码，我要求你根据它的代码重写一个python版本的claude code。要求：
1. python版本为3.12
2. 项目写在claude-code-python目录下，我已经创建好文件夹
3. 只重写核心功能，包括
（1）TUI前端界面：只需要包含基本的消息展示，用户对话框输入
（2）工具调用：只需要包括 文本文件读（只需要考虑文本文件，不需要图片/pdf或其他类型）、写、编辑、glob搜索、grep搜索、bash工具
（3）模型供应商只需要包括openai兼容的v1/chat/completions，用户只需要提供api_url，api_key, model_name
4. 最终效果目标：复刻claude code的编程agent功能，架构和执行逻辑需要与原始typescript版本的一致，，其他高级功能暂不需要
这是一个非常复杂的任务，加油开始干吧！

- 结果：基本框架搭好，但有很多bug，后端问题较少，前端问题较多

## Claude Code GLM-5

这个是claude-code-python源码，当我运行claude-code后，输入消息后提示Error: Query failed: Server disconnected without sending a response.修复该问题

- 结果：识别为HTTP/2连接问题，成功修复
---
这个是claude-code-python源码，当我运行claude-code后，输入消息后提示错误：

You这个代码仓库是干啥的

我来帮你查看这个代码仓库的内容和用途。

🔧 Bash
❌ Tool execution failed: 'command'

🔧 Glob
❌ Tool execution failed: 'pattern'

🔧 Glob
❌ Tool execution failed: 'pattern'

所有工具调用都报错，修复

- 结果：识别为工具调用累积错误问题，成功修复

---

/Users/MacbookAir/Downloads/Framework-Reading/claude-code目录是claude code 的typescript官方源码，但是官方并没有python版本。/Users/MacbookAir/Downloads/Framework-Reading/claude-code-python是python版重写的claude code，但仍有缺陷。我需要你根据typescript源码完善和修复重写的claude-code-python。要求：
1. python版本为3.12
2. 只需要核心功能，包括
（1）TUI（终端）前端界面：只需要包含基本的消息展示，用户对话框输入，前端布局需要和claude code 的typescript版本保持一致
（2）工具调用：只需要包括 文本文件读（只需要考虑文本文件，不需要图片/pdf或其他类型）、写、编辑、glob搜索、grep搜索、bash工具
（3）模型供应商只需要包括openai兼容的v1/chat/completions，用户只需要提供api_url，api_key, model_name
（4）提示词（包括但不限于系统提示词、各种组件需要的提示词、工具描述提示词等等），需要与claude code的typescript版本完全保持一致，即使用完全相同的提示词，不能存在任何差异。
3. 最终效果目标：复刻claude code的编程agent功能，代码架构和执行逻辑需要与原始typescript版本的一致，其他高级功能暂不需要
4. 目前这个任务已经完成了一个初版，在/Users/MacbookAir/Downloads/Framework-Reading/claude-code-python下，全面检查并修复claude-code-python的问题
5. 所有代码架构和代码逻辑，必须以typescript官方源码为准进行参考，记住python只是去重写typescript版本，python不能新增逻辑或与typescript版本逻辑不一致

目前claude-code-python还有很多不完善的地方，开始干吧，直到你认为修复到没有问题！

上面这段保存为@rewrite_instructions.md

tui命令报错claude-code --tui Error in stylesheet:
/Users/MacbookAir/Downloads/Framework-Reading/claude-code-python/claude_code/ui/app.css:9:12
修复该问题

- 结果：宣称修复
---
@rewrite_instructions.md
目前python版本的tui命令后（即claude-code --tui）后，前端界面完全不对，问题1：看不到输入框 问题2：颜色为蓝色，与官方typescript源码的橙色不一致3. 与官方布局不一致4. 官方的TUI界面为（粘贴字符串）

修复所有问题，记住多参考官方typescript源码

- 结果：宣称修复，但实际上此时的前端UI有很多错位bug
---
@rewrite_instructions.md
目前python版本的tui命令后（即claude-code --tui）后报错，错误为：
╭─ Error at /Users/MacbookAir/Downloads/Framework-Reading/claude-code-python/name:151:17
修复所有问题，必要时可以参考官方typescript源码

- 结果：宣称修复
---
@rewrite_instructions.md
目前python版本的tui命令后（即claude-code --tui）后,前端界面只有一个欢迎界面，看不到用户输入框，无法输入任何内容，修复这个问题

- 结果：宣称修复
---
@rewrite_instructions.md
目前python版本的tui命令后（即claude-code --tui）后,前端界面为全黑，修复这个前端问题

- 结果：宣称修复
---
@rewrite_instructions.md
目前python版本的tui命令后（即claude-code --tui）后,前端还存在问题：
问题1：欢迎界面的边框有错位
问题2：用户输入信息后，回车，界面会停住好几秒，才会有消息
问题3：agent的消息显示断断续续，比如先显示一个框，内容是："我是"，然后显示一个框，内容是："我是xx模型"，显然是bug

修复这三个问题

- 结果：宣称修复
---
@rewrite_instructions.md
目前python版本的tui命令后（即claude-code --tui）后,前端还存在问题：
问题1：欢迎界面左右两边中间没有完整的分割线，只有很短一段。最外围边框也有一小段断连
问题2：用户输入信息后，回车，界面会停住好几秒，消息仍然留在发送框，直到模型回复才会刷新
问题：agent的消息显示断断续续，比如先显示一个框，内容是："我是"，然后显示的第二个框内容才是完整的，内容是："我是xx模型..."，最终模型回复是两个框，显然是bug

修复这三个问题

- 结果：宣称修复
---
此时已经确信，GLM无论如何也修不好这些前端UI的bug，于是只能使用 Codex GPT-5.4

## Codex GPT-5.4

@rewrite_instructions.md
目前python版本的tui命令后（即claude-code --tui）后,前端还存在问题：
问题1：欢迎界面左右两边中间分割线不全，和外围边框不匹配
问题2：用户输入信息后，回车，界面会停住好几秒，消息仍然留在发送框，直到模型回复才会刷新，另外不需要“send”按钮，只要回车就可以
问题3：没有实时流式输出
问题4：没有消息滚动输出


工具调用显示可能也有潜在的问题，现在的前端就不是一个正常的AI agent的TUI该有的样子，你给我修改好，最终效果是TUI能够像ai agent显示消息那样正常。开始修改！

- 结果：部分修复，又出现问题
---
我试了一下，又发现几个问题：

左下角和右下角的快捷键提示不需要，quit和palette
欢迎框尺寸太大，尤其是高度太大
我问模型“探索一下仓库", 模型调用各种工具输出时，直接屏幕内容全黑
修复这些问题

- 没修好，继续问
---
我确定问题：工具调用的所有输出都是黑屏的，但是右边的下拉条似乎在动，好像是有输出占用空间，但是完全是黑的（颜色问题？还是什么）

- 没修好，继续问
---
还是没有显示，所有工具调用结果都无法显示，但是右侧下拉条不断下滑（好像有东西在产出，但是屏幕全黑），搜集尽可能多的资料，修复这个问题

- 结果：成功定位到布局问题，修复了黑屏
---
好了，所以总结一下之前一直没修好，这次修好的原因，总结到AGENTS.md文档里

- 更新AGENTS.md
---
现在的UI能正常工作，但是太简陋，有哪些textual的高级特性没用上

- GPT说了很多，但看起来有用的只有Collapsible：工具调用详情、工具输入参数、长输出预览都很适合折叠。AI agent TUI 常见做法就是“消息主干简洁，工具细节按需展开”。官方文档：https://textual.textualize.io/widgets/collapsible/

先改这个

- 完成
---
问题：当用户发送消息回车后，没有等待动画，转圈或者别的，很枯燥

- 完成
---
thinking动画和聊天框错位了

- 完成
---
两个问题：

行间距太大
不同块（用户输入，模型回答，工具调用）现在风格是一致的，能不能视觉上高级一点区分

- 没修好
---
> 此时实在没办法，截图扔给GPT看看，但实际上感觉作用并不大，一些细节（间距等问题）GPT基本感知不到

[Image #1] 首先，1. claude的消息是不用加底色的，保持和整体背景色一致 2. 每次工具调用消息和工具结果没必要分开（合并到一个）

[Image #1] 更改要求：1. Claude/You不必再加，因为已经能够区分 2. 左侧的橙色/绿色边线也不需要了

[Image #1] 1. 用户的历史消息底色不要用绿色了，用浅灰白一点的颜色， 绿色太难看 2. 工具显示为什么会有一些重复，比如bash find重复了2次，后面又紧跟着Rand find，这些重复没有必要 3. 工具调用左侧的白色边线没有必要，去掉 4. 用户历史消息/claude历史消息/工具消息/用户输入框左侧要对齐

还有一个问题，在生成滚动过程中（模型仍在响应），我无法手动使用滚动条滚上去先查看部分内容，会被硬拉回来。

问题：

用户历史消息块中文字和上下边框几乎没有空隙
工具显示块同理
现在行间距不统一，例如用户消息和claude消息之间，不同工具块之间，claude消息和工具块之间，要统一，且不能太大

[Image #1] 1.现在所有间距都太大了，适量缩小，2.另外工具调用隔几个之后突然间距变大

多个工具块间距会出现不均匀现象，同时claude消息和第一个工具块间距过小

- 这一次GPT终于识别到间距忽大忽小是因为组件设置问题，修复成功
---
TUI退出现在只限定输入exit一种方式，其他方式取消

> 此时前端UI功能已经正常，后续只需要一些修补工作，因此GPT暂时休息

## Opencode doubao-seed-code-2.0

@rewrite_instructions.md 现在python版的前端有几个问题：
1. 输入框上下箭头没反应，增加上下箭头切换历史信息功能，像linux命令行一样，要求历史信息重开程序也要保留
2. 输入框超过一行后无法自动变大，还是会挤在一行内
3. 输入框不支持框内换行（shift+enter）

- 宣称三个问题都修好了，结果三个问题全没修好。。

> 此时感觉doubao真的拉完了，于是再试试GLM-5

## Claude GLM-5

@rewrite_instructions.md 当前的vscode重写的claude code版本与原始typescript版本所有提示词是否完全一致，修复任何不一致的地方

现在claude-code-python当前前端输入框存在问题：

输入框文字和上下边框直接没有空隙
enter键应该是发送消息，但现在是变成了换行（不对），换行应该改成shift+enter
修复输入框的问题

> 此时GLM-5始终无法修复shift+enter框内换行问题，只能让gpt上


## GPT 5.4

这个项目的前端TUI输入框存在问题：
输入框回车后，上方显示Working工作中时，输入框右侧会出现一个色块，当用户输入第二条消息时，输入框会自动出现一次换行。修复输入框的问题

> 只要能准确无误地描述清楚前端问题现象，GPT-5.4大部分都能修复成功

这个项目目前的前端TUI存在问题：macos item2下command+c无法复制到剪贴板，显示mouse reporting。使用textual控制复制到剪贴板的行为（cmmand+c[macos]或者ctrl+c[其他系统]），不要依赖系统快捷键，（防止在macos,linux,windows)迁移问题

- 成功修复无法复制粘贴问题



