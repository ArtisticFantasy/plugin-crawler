import pymysql
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import requests as rq
import time
import re

proxies={
    "http":"socks5://127.0.0.1:7890",
    "https":"socks5://127.0.0.1:7890",
}
header={
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
    "Connection": "keep-alive",
    "Accept-Language":"zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Accept-Encoding":"gzip, deflate, br",
    "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Host":"www.baidu.com",
    #"Cookie":""
}
llm_words = [
    "大模型", "大语言模型","自然语言处理","[^a-z]llm[^a-z]","chatgpt","[^a-z]gpt[^a-z]","[^a-z]glm[^a-z]","grand language model",
    "[^a-z]nlp[^a-z]","natural language processing",   #防止llm,gpt,glm,nlp出现在单词中
    "large language model","large model","generative pre-training transformer",
    "大規模言語モデル",
    "grand modèle de langage",
    "großes Sprachmodell",
    "언어 모델"
]
plugin_words = [
    "plugin","插件","webui","web ui","extension",
    "扩展","[^a-z]ui[^a-z]" #防止ui出现在单词中
]

def get_real_url(redirect_url): #获取百度链接的真实地址
    try:
        r=rq.get(redirect_url,proxies=proxies,allow_redirects=False,headers=header)
    except:
        return ""
    if r.status_code==404:
        print("Error: Connection rejected when fetching the real url of {}".format(redirect_url))
        return ""
    return r.headers['Location']

def get_title(url): #获取url对应的title
    try:
        r=rq.get(url,proxies=proxies,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',"Connection": "close"})
    except:
        return ""
    if r.status_code==404:
        print("Error: Connection rejected when fetching the title of {}".format(url))
        return ""
    soup=BeautifulSoup(r.text,'lxml')
    if soup.title!=None:
        res=soup.title.string
    else: res=""
    return res

def get_llm_url(word,url_res,title_res): #百度爬虫获取相关url
    pn=0
    cnt=0
    ids=[]
    loss_cnt=0
    while True:
        crawl_url="https://www.baidu.com/s?wd={}&pn={}".format(word,pn)
        print("Crawling: {}...".format(crawl_url))
        try:
            r=rq.get(crawl_url, proxies=proxies, headers=header)
        except:
            pn+=10
            continue
        if r.status_code==404:
            print("Error: Connection rejected when crawling {}".format(crawl_url))
            return url_res
        soup=BeautifulSoup(r.text,"lxml")
        result_list=soup.find_all('div',tpl=re.compile('se_.*'))
        recom_list=soup.find('div',tpl='recommend_list')
        flag=False
        for result in result_list:
            if result.get('mu'):
                #print(result['mu'])
                tmp=result['mu']
            else: tmp=get_real_url(result.a['href'])
            if tmp=="": continue
            tid=int(result['id'])
            if recom_list!=None and int(recom_list['id'])<tid: tid-=1 #防止推荐列表偏置
            if pn>=10 and tid<=10 : #遇到tid<10且pn>=0，说明已经爬取完所有页面，直接退出即可
                flag=True
                break
            if not tid in ids: #遇到当前轮新的url
                ids.append(tid)
                if not tmp in url_res:  # 遇到新url，更新结果
                    tit=get_title(tmp)
                    if tit=="": continue
                    if not tit in title_res:
                        url_res.append(tmp)
                        title_res.append(tit)
                        cnt+=1
                #else: print(tid,tmp)
        print("Crawled {} new urls".format(cnt))
        if flag: break
        time.sleep(0.2) #休息0.2秒，防止被封IP
        loss=False
        for i in range(pn+1,pn+11): #注意，pn只能表示页数，其实际含义不包括第几个搜索结果！
            if not i in ids: #当前页存在丢失
                #print(i)
                loss=True
                break
        if not loss: pn+=10
        else:
            loss_cnt+=1
            if loss_cnt>2: #3次查询同一页面没有更多信息，可能存在反爬或者网络问题，不再尝试
                pn+=10
                loss_cnt=0
    print("Finally crawled {} new urls in total, and now we have {} urls".format(cnt,len(url_res)))
    return url_res,title_res

githubpat = re.compile('https?://(?:www\.)?github\.com/[\.\w-]+/[\.\w-]+',re.ASCII) #匹配github repo链接（注意不匹配中文）
def get_github_links(alltext,pos): #获取github repo links 并且要与plugin关键词之间的距离不超过dis
    dis=500 #关键词与相关链接的最大距离（字节）
    it=githubpat.finditer(alltext)
    i=0
    res=[]
    for match in it:
        p=match.start()
        while i+1<len(pos) and pos[i+1]<p: i+=1 #找到小于当前匹配位置的最大的pos
        if p-pos[i]<=dis or (i+1<len(pos) and pos[i+1]-p<=dis): res.append(match.group(0)) #与plugin关键词之间的距离不超过dis
    return list(set([item[:-4] if item[-4:]==".git" else item for item in res])) #删除末尾.git

def check_llm_plugin_relation(url): #检查是否与llm开源插件相关（可能检查机制还需改进？）
    try:
        r=rq.get(url, proxies=proxies, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',"Connection": "close"})
    except:
        print("Request Error!")
        return False,None,[]
    if r.status_code==404:
        print("Error: Connection rejected when checking {}".format(url))
        return False,None,[]
    soup = BeautifulSoup(r.text, 'lxml')
    if githubpat.fullmatch(url): #对于github repo，直接读readme的内容
        readmemkd=soup.find('article',class_=re.compile("markdown-body.*"),itemprop="text")
        if readmemkd!=None: alltext=' '.join(str(readmemkd).split('\n'))
        else: alltext=""
    else: #否则由于格式未知，只能读body的内容
        if soup.body!=None:
            alltext=' '.join(str(soup.body).split('\n'))
        else: alltext=""
    lowalltext=alltext.lower()
    #分别判断是否满足LLM相关，插件相关和开源相关
    flag1=False
    for item in llm_words:
        if re.search(r">[^<]*?({})[^>]*?<".format(item),lowalltext): #只匹配标签内部的text，防止标签属性包含相关词
            flag1=True
            break
    flag2 = False
    pos=[]
    for item in plugin_words:
        if re.search(r">[^<]*?({})[^>]*?<".format(item),lowalltext): #只匹配标签内部的text，防止标签属性包含相关词
            it=re.finditer(r">[^<]*?({})[^>]*?<".format(item),lowalltext)
            pos.extend([match.start(1) for match in it])
            flag2 = True
            break
    pos=list(set(pos))
    pos.sort()
    return flag1&flag2,alltext,pos #返回plugin相关出现位置


def update_url_and_title(): #获取最新的url和title
    df = pd.read_excel("crawled_url.xlsx")
    url_data = df['url'].tolist()
    title_data = df['title'].tolist()
    urls, titles = get_llm_url("LLM 插件", url_data, title_data)
    data = pd.DataFrame({"url": urls, "title": titles})
    data.to_excel("crawled_url.xlsx", index=False)


fin_tot=0

def get_github_repos(conn,cursor,cnt,tot,url): #递归搜索url，得到related github repos
    global fin_tot
    print("[Process {}/{} | {} related repos] Checking url: {}...".format(cnt, tot, fin_tot, url))
    query="SELECT COUNT(*) FROM github_repo WHERE url = '{}' and related IS NOT NULL".format(url)
    cursor.execute(query)
    num,=cursor.fetchone()
    if num>0: #数据库中存在此记录，说明已经递归过该url了
        print("[Process {}/{} | {} related repos] Already searched!".format(cnt, tot, fin_tot))
        return
    related,alltext,pos=check_llm_plugin_relation(url)
    if related:
        links_t = get_github_links(alltext,pos)
        for link in links_t:   #将所有内部github repo插入mysql中（先将子节点插入数据库再更改或插入父节点结果，从而满足异常中断后当前递归状态能被保存）
            if githubpat.fullmatch(link):
                query="SELECT COUNT(*) FROM github_repo WHERE url = '{}'".format(link)
                cursor.execute(query)
                num,=cursor.fetchone()
                if num==0:
                    query = "INSERT INTO github_repo (url,related) VALUES('{}',NULL)".format(link)
                    cursor.execute(query)
                    conn.commit()
        print("[Process {}/{} | {} related repos] This url is related with the open source LLM plugins.".format(cnt,tot,fin_tot))
        if githubpat.fullmatch(url): #自身就是github repo
            fin_tot+=1
            query = "SELECT COUNT(*) FROM github_repo WHERE url = '{}'".format(url)
            cursor.execute(query)
            num,=cursor.fetchone()
            if num==0:    #不存在此url记录，插入，否则直接更新即可
                query = "INSERT INTO github_repo (url,related) VALUES('{}',1)".format(url)
            else:
                query = "UPDATE github_repo SET related = 1 WHERE url = '{}'".format(url)
            cursor.execute(query)
            conn.commit()
            print("[Process {}/{} | {} related repos] Find {} related github repos in total.".format(cnt,tot,fin_tot,fin_tot))
        for link in links_t:
            get_github_repos(conn,cursor,cnt,tot,link) #递归搜索
    else:
        if githubpat.fullmatch(url):
            query = "SELECT COUNT(*) FROM github_repo WHERE url = '{}'".format(url)
            cursor.execute(query)
            num,=cursor.fetchone()
            if num==0:    #不存在此url记录，插入，否则直接更新即可
                query = "INSERT INTO github_repo (url,related) VALUES('{}',0)".format(url)
            else:
                query = "UPDATE github_repo SET related = 0 WHERE url = '{}'".format(url)
            cursor.execute(query)
            conn.commit()
        print("[Process {}/{} | {} related repos] This url isn't related with the open source LLM plugins.".format(cnt,tot,fin_tot))

def create_database(): #创建数据库
    DB_CONFIG={
        "user":"root",
        "password":"root",
        "host":"127.0.0.1",
        "charset":"utf8mb4"
    }
    conn=pymysql.connect(**DB_CONFIG)
    cursor=conn.cursor()
    cursor.execute("DROP DATABASE IF EXISTS plugin_crawler")
    cursor.execute("CREATE DATABASE IF NOT EXISTS plugin_crawler")
    cursor.execute("USE plugin_crawler")
    cursor.execute("CREATE TABLE IF NOT EXISTS github_repo ("
                   "id INT AUTO_INCREMENT PRIMARY KEY,"
                   "url VARCHAR(256) NOT NULL UNIQUE,"
                   "related INT ) DEFAULT CHARACTER SET = utf8mb4")
    cursor.close()
    conn.commit()
    conn.close()
    print("Create database succefully!")

def get_related_links(): #获取最终的related github repo links
    global fin_tot
    df = pd.read_excel("crawled_url.xlsx")
    url_data = df['url'].tolist()
    tot=len(url_data)
    cnt=0
    DB_CONFIG = {
        "user": "root",
        "password": "root",
        "host": "127.0.0.1",
        "database": "plugin_crawler",
        "charset": "utf8mb4"
    }
    conn = pymysql.connect(**DB_CONFIG)
    cursor=conn.cursor()
    query="SELECT COUNT(*) FROM github_repo WHERE related = 1"
    cursor.execute(query)
    fin_tot,=cursor.fetchone()
    query = "SELECT url FROM github_repo WHERE related IS NULL"
    cursor.execute(query)
    urls=cursor.fetchall()
    if len(urls)>0:
        print("The recursion didn't finish last time. Precalculation Start!") #上次递归未结束，从上次位置继续
        for url, in urls:
            get_github_repos(conn, cursor, "precal", tot, url)
        print("Precalculation finished.")
    for url in url_data:
        cnt+=1
        print("[Process {}/{} | {} related repos] Main url: {}...".format(cnt,tot,fin_tot,url))
        get_github_repos(conn,cursor,cnt,tot,url)
    cursor.close()
    conn.close()

def output_related_repos(): #输出related github repos到文件
    DB_CONFIG = {
        "user": "root",
        "password": "root",
        "host": "127.0.0.1",
        "database": "plugin_crawler",
        "charset": "utf8mb4"
    }
    conn=pymysql.connect(**DB_CONFIG)
    cursor=conn.cursor()
    query="SELECT url FROM github_repo WHERE related = 1"
    cursor.execute(query)
    data=cursor.fetchall()
    cursor.close()
    conn.close()
    result=[x for x, in data]
    data=pd.DataFrame({"related repos":result})
    data.to_excel("related_github_repos.xlsx",index=False)
    print("Write the total of {} results to excel successfully!".format(len(result)))

if __name__=='__main__':
    print("Four modes")
    print("1: Crawl www.baidu.com to update urls and titles.")
    print("2: Drop the original database and recreate it.")
    print("3: Get related github repos and write them to database.")
    print("4: Output related github repos into excel.")
    mode=int(input("Please input which mode you want to use (1-4): "))
    if mode==1:
        update_url_and_title()
    elif mode==2:
        create_database()
    elif mode==3:
        get_related_links()
    elif mode==4:
        output_related_repos()
    else: print("Wrong input!")