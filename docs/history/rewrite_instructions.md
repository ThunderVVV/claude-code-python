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