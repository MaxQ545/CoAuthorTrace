# SearchBox Typeahead 功能设计文档

**日期**: 2026-02-05
**功能**: 为 SearchBox 组件添加搜索建议（Typeahead）功能

## 功能目标

用户输入时实时显示匹配的作者及其机构，点击建议项后跳转至 `/author/:id`。

## 核心需求

- 实现 300ms 防抖处理
- 使用 Tailwind CSS 渲染下拉列表
- 展示"姓名"及下方的"机构名称"
- 支持键盘上下键选择及回车跳转
- 点击外部自动关闭列表
- 保留原有搜索按钮功能

## 设计方案

### 1. 整体架构和状态管理

**组件架构**

SearchBox 组件保持为受控组件，新增以下状态：
- `suggestions` - 存储 API 返回的作者建议列表（最多10条）
- `showSuggestions` - 控制下拉列表的显示/隐藏
- `selectedIndex` - 记录键盘选中的建议项索引（-1 表示未选中）
- `isLoadingSuggestions` - 建议加载状态

**防抖处理**

使用 `useEffect` + `setTimeout` 实现 300ms 防抖：
- 监听 `query` 变化
- 当 `query.length >= 2` 时，延迟 300ms 后调用 API
- 清理函数取消之前的定时器，避免重复请求

**双重交互模式**

1. **Typeahead 模式**：用户输入 → 显示建议 → 点击或键盘选择 → 跳转到 `/author/:id`
2. **传统搜索模式**：用户输入 → 点击搜索按钮或直接回车（未选中建议时）→ 调用 `onSearch(query)` → 跳转到搜索结果页

### 2. UI 设计和 Tailwind 样式

**下拉列表布局**

使用绝对定位的下拉菜单，紧贴在输入框下方：
- 容器：`absolute top-full left-0 right-0 mt-1 z-50`
- 背景：`bg-background border border-border rounded-lg shadow-lg`
- 列表项结构：
  - 作者姓名：`text-foreground font-medium`（主要文本，较大字号）
  - 机构名称：`text-muted-foreground text-sm`（次要文本，较小字号，灰色）
  - 悬停/选中状态：`bg-muted`（鼠标悬停或键盘选中时的背景高亮）

**建议项内容展示**

每个建议项显示：
- **第一行**：作者姓名（`display_name`）
- **第二行**：主要机构（优先使用 `primary_institution_name`，其次 `last_known_institution_name`）
- 如果没有机构信息，显示"未知机构"

**加载和空状态**

- 加载中：显示旋转图标 + "搜索中..."
- 无结果：显示 "未找到匹配的作者"
- API 错误：静默失败，关闭下拉列表

### 3. 键盘交互和事件处理

**键盘导航**

监听 `onKeyDown` 事件，实现以下快捷键：
- **ArrowDown（下键）**：`selectedIndex + 1`，到达底部后停止
- **ArrowUp（上键）**：`selectedIndex - 1`，到达顶部后停止
- **Enter（回车键）**：
  - 如果 `selectedIndex >= 0`（已选中建议项）：阻止表单提交，跳转到 `/author/:id`
  - 如果 `selectedIndex === -1`（未选中）：触发表单提交，调用 `onSearch(query)`
- **Escape（ESC键）**：关闭下拉列表，清空选中索引

**点击外部关闭**

使用 `useEffect` + `document.addEventListener('mousedown')` 实现：
- 为组件根元素添加 `ref`
- 监听全局点击事件，判断点击位置是否在组件外部
- 如果在外部，关闭下拉列表

**路由跳转**

- 使用 React Router 的 `useNavigate()` hook
- 点击建议项或键盘选中后回车跳转到 `/author/:id`

### 4. 错误处理和边界情况

**API 调用错误处理**

- 使用 try-catch 捕获 API 错误
- 错误时静默失败，关闭下拉列表，不打断用户输入
- 在控制台记录错误（`console.error`）方便调试

**边界情况处理**

1. **快速输入/删除**：防抖机制自动处理，取消未完成的请求
2. **输入长度 < 2**：不调用 API，隐藏下拉列表
3. **空格处理**：使用 `query.trim()` 判断有效输入
4. **建议列表为空**：显示"未找到匹配的作者"提示
5. **组件卸载时清理**：在 `useEffect` 清理函数中取消定时器和事件监听器

**性能优化**

- API 限制 `limit=10` 减少数据传输
- 防抖 300ms 减少请求频率
- 只在必要时更新状态（避免不必要的重渲染）

## 技术参数

- **最小输入长度**: 2 个字符
- **建议数量**: 10 条
- **防抖延迟**: 300ms
- **API 端点**: `/api/v1/authors/search`
- **路由跳转**: `/author/:id`

## 实施要点

1. 修改 `frontend/src/components/SearchBox.jsx`
2. 导入 `useNavigate` from `react-router-dom`
3. 导入 `api` from `../api/client.js`
4. 新增状态管理和事件处理逻辑
5. 添加下拉列表 UI 组件
6. 实现键盘导航和点击外部关闭
7. 保持向后兼容性（原有 props 和行为不变）
