# Plugin Crawler

本程序用于爬取LLM相关的第三方插件，并输出到excel中。

## 功能介绍

程序大致分为以下四个功能：

### 1.百度搜索爬虫获取相关的url和title

模拟百度搜索 “LLM 插件”，并不断翻页记录查询得到的真实url和对应页面title。如果一页爬取内容不完整（不到10个），则会至多重复爬取两次，两次过后如果仍不完整则放弃该页面爬取。

由于国内镜像复制站比较多，所以在对url去重的同时，也要对title去重，最终将结果保存至 crawled_url.xlsx。

**注意：及时刷新浏览器获取最新cookie并更换，以免出现百度反爬机制！**

### 2.创建数据库

删除旧版数据库，并创建数据库以完成功能3的记忆化搜索功能。

数据库名称为plugin_crawler，在其中创建了表github_repo，用于存储爬虫得到的github仓库信息。

表格式如下：

|               id               |             url              | related |
| :----------------------------: | :--------------------------: | :-----: |
| INT PRIMARY KEY AUTO_INCREMENT | VARCHAR(256) NOT NULL UNIQUE |   INT   |

其中id是主键，代表行标号，url表示github repo的url，related表示是否是LLM第三方插件相关（0表示无关，1表示有关）

### 3.递归爬虫搜索与相关性判断

从crawled_url.xlsx中读取功能1爬虫得到的数据，并从页面中找到github仓库网站，进行递归查找（出于安全性考虑，只对github仓库链接递归）。

每访问一个新的url，通过关键词判断当前页面是否与LLM以及第三方插件相关（只判断html text中的内容，不判断html标签中的内容，防止出现误判）

LLM相关关键词：

```
"大模型", "大语言模型","自然语言处理","[^a-z]llm[^a-z]","[^a-z]gpt[^a-z]","[^a-z]glm[^a-z]","chatgpt",
"grand language model","[^a-z]nlp[^a-z]","natural language processing","large language model",
"large model","generative pre-training transformer","大規模言語モデル","grand modèle de langage",
"großes Sprachmodell","언어 모델"
```

第三方插件相关关键词：

```
"插件","扩展"，"plugin"，"webui","web ui","extension","[^a-z]ui[^a-z]"
```

其中部分采用正则表达式判断是因为防止缩写出现在单词内造成误判（比如**ui**出现在req**ui**rements中）。

在爬虫时，只会对**与插件相关关键词出现位置距离小于等于500字节**的当前页面上的github repo链接进行递归（对于非github repo，考虑整个body中的内容，否则考虑README.md中的内容，通过正则表达式匹配github repo链接），防止递归到无关链接加大计算复杂度。

递归采用记忆化搜索，将递归过的链接动态和即将递归的链接动态写入数据库，防止重复计算。

#### Feature

在递归父url时提前将儿子url写入数据库（未访问到的related设为NULL），以随时保存当前递归状态，可以随时终止程序。当程序开始运行时检测到存在related为NULL的情况，说明上次递归未完全结束，于是额外进行一轮Precalculation计算优先递归搜索这些related为NULL的url。

**注意：由于github存在软墙，记得更改代理设置！**

### 4.输出相关github repos至excel

将数据库中related为1的url全部输出到 related_github_repos.xlsx。

## 使用说明

1.安装本程序依赖库，如 pandas, numpy, re, bs4, pymysql 等。

2.终端执行 ```python plugin_crawler.py```

3.按照提示输入1到4的一个数字以选择模式