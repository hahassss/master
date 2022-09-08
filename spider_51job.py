import json
import re
import time
import random
import threading
from queue import Queue
from pymongo import MongoClient
from selenium import webdriver

THREAD_NUM = 1  # 进程数量，几个窗口几个进程


def random_sleep():
    time.sleep(random.randrange(100, 501) / 1000)


def thread_run(driver_list, q, lock, client, keyword):
    driver_list_len = len(driver_list)
    collection = client['Job51'][keyword]
    collection.drop()  # 删除原有数据重新获取
    for i in range(driver_list_len):
        threading.Thread(target=get_data, args=(driver_list[i], q, lock, collection)).start()


def get_chrome_driver():
    options = webdriver.ChromeOptions()

    prefs = {
        'profile.default_content_setting_values': {  # 禁止加载某些资源或功能，提高访问速度
            'images': 2,  # 图片
            # 'javascript': 2,  # js
            'permissions.default.stylesheet': 2,  # css

        }
    }
    options.add_argument(r"user-data-dir=C:\Users\ADMINTENG\AppData\Local\Google\Chrome\User Data")  # 使用用户数据通过爬虫拦截
    options.add_experimental_option('prefs', prefs)
    options.add_experimental_option("excludeSwitches", ['enable-automation'])  # 不显示自动测试
    chrome_driver = r'C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe'  # chromedriver的文件位置

    driver_list = list()
    for i in range(THREAD_NUM):  # 打开多个浏览器窗口
        driver = webdriver.Chrome(executable_path=chrome_driver, options=options)
        driver.get('https://search.51job.com')
        driver_list.append(driver)
        time.sleep(1)
    time.sleep(2)
    return driver_list


def get_queue(driver, keyword):
    driver.get(f'https://www.51job.com/')
    random_sleep()
    driver.get(f'view-source:https://search.51job.com/list/000000,000000,0000,00,9,99,{keyword},2,1.html')
    re_data = re.findall('total_page":"(.*?)"', driver.page_source)
    if not re_data:
        print("未获取到有效信息！请联系管理员处理！")
        time.sleep(30)
        random_sleep()
        return get_queue(driver, keyword)
    page_number = int(re_data[0])
    print(f'共找到 {page_number} 页与 {keyword} 相符的职位')

    q = Queue()
    for i in range(1, page_number + 1):
        q.put(f'view-source:https://search.51job.com/list/000000,000000,0000,00,9,99,{keyword},2,{i}.html')
    for i in range(THREAD_NUM):
        q.put(None)
    return q


def start(keyword):
    client = MongoClient()
    driver_list = get_chrome_driver()
    q = get_queue(driver_list[0], keyword)
    lock = threading.Lock()  # 线程锁
    thread_run(driver_list, q, lock, client, keyword)
    if q.qsize() != 0:
        q.join()  # 等待线程执行完毕
    client.close()


def get_data(driver, q, lock, collection):
    """
    :param driver: 浏览器窗口
    :param q:  队列
    :param lock: 线程锁
    :param collection: 数据库
    :return:
    """
    # 多个进程或线程使用同一个窗口时，可能会造成数据相同（异步）
    while True:
        page_url = q.get()
        try:
            if page_url is None:  # 生产者与消费者速度不一致解决方案
                break
            driver.get(page_url)
            try:
                data = driver.find_element_by_xpath(
                    '/html/body/table/tbody/tr[469]/td[2]').text
            except Exception as e:
                _ = e
                print("未获取到有效信息！请联系管理员处理！")
                q.put(page_url)
                time.sleep(30)
                random_sleep()  # 随机睡眠
                continue
            list_all = re.findall('({"type".*?})', data)
            # 定义    '公司名称', '职位', '薪资', '学历要求',
            # '工作经验', '公司地点','所招人数','公司性质',
            # '公司规模', '公司类型', '公司福利', '发布时间'
            for info_str in list_all:
                info_dict = json.loads(info_str)
                list_4 = info_dict.get('attribute_text')
                # 过滤掉无标注经验或学历要求的数据
                if len(list_4) < 4:
                    continue
                company_name = info_dict.get('company_name')
                job_name = info_dict.get('job_name').replace('\\\\', '')
                provide_salary = info_dict.get('providesalary_text')
                if not provide_salary:  # 过滤掉无明确薪资的数据
                    continue
                academic_re = list_4[2]
                experience = list_4[1].replace('\\\\\\\\', '')
                workarea = list_4[0]
                recruiting_num = list_4[3]
                companytype = info_dict.get('companytype_text')
                companysize = info_dict.get('companysize_text')
                companyind = info_dict.get('companyind_text')
                if companyind:
                    companyind = companyind.replace('\\\\', '')
                jobwelf_list = info_dict.get('jobwelf_list')
                updatedate = info_dict.get('updatedate')
                data_item = {
                    '公司名称': company_name,
                    '职位': job_name,
                    '薪资': provide_salary,
                    '学历要求': academic_re,
                    '工作经验': experience,
                    '公司地点': workarea,
                    '所招人数': recruiting_num,
                    '公司性质': companytype,
                    '公司规模': companysize,
                    '公司类型': companyind,
                    '公司福利': jobwelf_list,
                    '发布时间': updatedate
                }

                try:
                    with lock:
                        collection.insert(data_item)
                except Exception as e:
                    print(e)
                    print(f'写入失败：{data_item}')
            page = page_url.split(',')[-1][:-5]
            print(f'第{page}页爬取写入完成！')
        except Exception as e:
            print(e)
        finally:
            q.task_done()
    driver.close()


if __name__ == '__main__':
    start('销售')
    if input('start(y/n):') == 'y':
        start('设备维护工程师')

        # start('UI设计师')

