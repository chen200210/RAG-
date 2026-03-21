from selenium import webdriver
from bs4 import BeautifulSoup
import mysql
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import SessionNotCreatedException
import time
import random
from pathlib import Path
import datetime
import os


class Spider(object):

    def __init__(self):
        # 创建数据库对象
        self.__sql = mysql.MySql()
        
        # 配置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # 添加UA
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        # 添加其他反爬参数
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        profile_dir = os.getenv("CHROME_USER_DATA_DIR")
        if not profile_dir:
            profile_dir = str(Path(__file__).resolve().parent / ".chrome_profile")
        chrome_options.add_argument(f'--user-data-dir={profile_dir}')
        chrome_options.add_argument('--profile-directory=Default')
        
        try:
            self.__driver = self.__create_driver(chrome_options)
            # 执行CDP命令
            self.__driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
        except Exception as e:
            print(f"Browser initialization error: {e}")
            raise e
        
        # 隐式等待
        self.__driver.implicitly_wait(20)

        try:
            self.__driver.get("https://www.zhipin.com/")
            time.sleep(random.uniform(1, 2))
            self.__maybe_wait_for_manual("首页")
        except Exception:
            pass
        
        # 关键词
        self.__keyword = ['Android']
        self.__today = datetime.date.today().strftime('%Y-%m-%d')

    def __del__(self):
        # 关闭无头浏览器，减少内存损耗
        try:
            if hasattr(self, "_Spider__driver") and self.__driver is not None:
                self.__driver.quit()
        finally:
            try:
                self.__sql.close()
            except Exception:
                pass

    def __create_driver(self, chrome_options: Options):
        env_driver = os.getenv("CHROMEDRIVER_PATH")
        if env_driver:
            return webdriver.Chrome(service=Service(env_driver), options=chrome_options)

        local_driver = Path(__file__).resolve().parent / "chromedriver.exe"
        if local_driver.exists():
            try:
                return webdriver.Chrome(service=Service(str(local_driver)), options=chrome_options)
            except SessionNotCreatedException:
                pass

        try:
            return webdriver.Chrome(options=chrome_options)
        except Exception:
            from webdriver_manager.chrome import ChromeDriverManager
            return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    def __maybe_wait_for_manual(self, page_hint: str) -> bool:
        current_url = self.__driver.current_url or ""
        title = self.__driver.title or ""
        html = self.__driver.page_source or ""

        need_manual = False
        if ("login" in current_url) or ("passport" in current_url) or ("captcha" in current_url) or ("verify" in current_url):
            need_manual = True
        if ("登录" in title) or ("安全验证" in title):
            need_manual = True
        if ("扫码登录" in html) or ("安全验证" in html) or ("验证码" in html) or ("请完成验证" in html):
            need_manual = True

        if not need_manual:
            return False

        print(f">>>检测到需要手动登录/验证页面: {page_hint}")
        print(f">>>当前URL: {current_url}")

        if os.getenv("AUTO_SKIP_BLOCKED", "0") == "1":
            return False

        input(">>>请在浏览器中完成登录/验证后，回到控制台按 Enter 继续...")
        return True

    # 设置爬取关键词
    def setKeyword(self, keyword):
        self.__keyword = []
        if isinstance(keyword, list):
            self.__keyword = keyword
        else:
            var = str(keyword)
            var.strip()
            if " " in var:
                keyword_list = var.split(' ')
                self.__keyword = keyword_list
            else:
                self.__keyword.append(var)

    # 获取所有关键词
    def getKeyword(self):
        return self.__keyword

    # 爬虫方法
    def run(self):

        print(">>>开始获取...")

        # 城市json
        cities = [{"name": "北京", "code": 101010100, "url": "/beijing/"},
                  {"name": "上海", "code": 101020100, "url": "/shanghai/"},
                  {"name": "广州", "code": 101280100, "url": "/guangzhou/"},
                  {"name": "深圳", "code": 101280600, "url": "/shenzhen/"},
                  {"name": "杭州", "code": 101210100, "url": "/hangzhou/"},
                  {"name": "天津", "code": 101030100, "url": "/tianjin/"},
                  {"name": "西安", "code": 101110100, "url": "/xian/"},
                  {"name": "苏州", "code": 101190400, "url": "/suzhou/"},
                  {"name": "武汉", "code": 101200100, "url": "/wuhan/"},
                  {"name": "厦门", "code": 101230200, "url": "/xiamen/"},
                  {"name": "长沙", "code": 101250100, "url": "/changsha/"},
                  {"name": "成都", "code": 101270100, "url": "/chengdu/"},
                  {"name": "郑州", "code": 101180100, "url": "/zhengzhou/"},
                  {"name": "重庆", "code": 101040100, "url": "/chongqing/"},
                  {"name": "佛山", "code": 101280800, "url": "/foshan/"},
                  {"name": "合肥", "code": 101220100, "url": "/hefei/"},
                  {"name": "济南", "code": 101120100, "url": "/jinan/"},
                  {"name": "青岛", "code": 101120200, "url": "/qingdao/"},
                  {"name": "南京", "code": 101190100, "url": "/nanjing/"},
                  {"name": "东莞", "code": 101281600, "url": "/dongguan/"},
                  {"name": "福州", "code": 101230100, "url": "/fuzhou/"}]
        # 总记录数
        all_count = 0
        # 关键词爬取
        for key in self.__keyword:
            print('>>>当前获取关键词: "{}"'.format(key))
            # 单个关键词爬取记录数
            key_count = 0
            # 每个城市爬取
            for city in cities:
                print('>>>当前获取城市: "{}"'.format(city['name']))
                # 记录每个城市爬取数据数目
                city_count = 0
                # 只获取前十页
                urls = ['https://www.zhipin.com/c{}/?query={}&page={}&ka=page-{}'
                            .format(city['code'], key, i, i) for i in range(1, 11)]
                # 逐条解析
                for url in urls:
                    try:
                        # 随机延时
                        time.sleep(random.uniform(2, 5))
                        
                        self.__driver.get(url)
                        if self.__maybe_wait_for_manual(url):
                            self.__driver.get(url)
                        # 添加随机滚动
                        self.__random_scroll()
                        
                        html = self.__driver.page_source
                        bs = BeautifulSoup(html, 'html.parser')
                        # 主要信息获取
                        job_all = bs.find_all('div', {"class": "job-primary"})
                        if not job_all:
                            if self.__maybe_wait_for_manual(f"列表为空: {url}"):
                                self.__driver.get(url)
                                self.__random_scroll()
                                html = self.__driver.page_source
                                bs = BeautifulSoup(html, 'html.parser')
                                job_all = bs.find_all('div', {"class": "job-primary"})
                            if not job_all:
                                print(f">>>列表为空，跳过: {url}")
                                continue

                        # 解析页面
                        for job in job_all:
                            # 工作名称
                            job_name = job.find('span', {"class": "job-name"}).get_text()
                            # 工作地点
                            job_place = job.find('span', {'class': "job-area"}).get_text()
                            # 工作公司
                            job_company = job.find('div', {'class': 'company-text'}).find('h3', {'class': "name"}).get_text()
                            # 公司规模
                            job_scale = job.find('div', {'class': 'company-text'}).find('p').get_text()
                            # 工作薪资
                            job_salary = job.find('span', {'class': 'red'}).get_text()
                            # 工作学历
                            job_education = job.find('div', {'class': 'job-limit'}).find('p').get_text()[-2:]
                            # 工作经验
                            job_experience = job.find('div', {'class': 'job-limit'}).find('p').get_text()
                            # 工作标签
                            job_label = job.find('a', {'class': 'false-link'}).get_text()
                            # 技能要求
                            job_skill = job.find('div', {'class': 'tags'}).get_text().replace("\n", " ").strip()
                            # 福利
                            job_welfare = job.find('div', {'class': 'info-desc'}).get_text().replace("，", " ").strip()

                            #职位类型 追加
                            type=key
                            job_url = ""
                            try:
                                a_tag = job.find('a', {'class': 'primary-box'})
                                if a_tag and a_tag.get('href'):
                                    job_url = a_tag.get('href')
                                elif job.find('a') and job.find('a').get('href'):
                                    job_url = job.find('a').get('href')
                            except Exception:
                                job_url = ""

                            # 数据存储
                            self.__sql.saveData(job_name, job_place, job_company, job_scale, job_salary, job_education,
                                                 job_experience,
                                                 job_label,
                                                 job_skill,
                                                 job_welfare,type, job_url=job_url, create_time=self.__today)
                            # 统计记录数
                            print(job_name, job_place, job_company, job_scale, job_salary, job_education,
                                                 job_experience,
                                                 job_label,
                                                 job_skill,
                                                 job_welfare)
                            city_count = city_count + 1
                        key_count = key_count + city_count
                    except Exception as e:
                        print(f"Error while scraping: {e}")
                        continue
                all_count = all_count + key_count

                print('>>>城市: "{}" 获取完成...获取数据: {} 条'.format(city['name'], city_count))
            print('>>>关键词: "{}" 获取完成...获取数据: {} 条'.format(key, key_count))
        print(">>>全部关键词获取完成...共获取 {} 条数据".format(all_count))

    def __random_scroll(self):
        """随机滚动页面"""
        total_height = self.__driver.execute_script("return document.body.scrollHeight")
        for i in range(3):
            target_height = random.randint(0, total_height)
            self.__driver.execute_script(f"window.scrollTo(0, {target_height});")
            time.sleep(random.uniform(0.5, 1.5))


if __name__ == '__main__':
    spider = Spider()
    keywords_env = os.getenv("KEYWORDS")
    if keywords_env:
        spider.setKeyword([k.strip() for k in keywords_env.split(",") if k.strip()])
    spider.run()
