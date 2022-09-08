# encoding:utf-8
import os
import random
import sqlite3
import pandas
import pyecharts
import jieba
import numpy as np
from pyecharts import Geo
from pyecharts import Pie
import matplotlib.pylab as plt
from pymongo import MongoClient
from wordcloud import WordCloud


class View:
    def __init__(self, keyword):
        self.keyword = keyword

        # 初始化MongoDB数据库
        try:
            self.client = MongoClient()
            self.collection = self.client['Job51'][self.keyword]
        except Exception as e:
            print(e)
            print("初始化MongoDB数据库失败！\n退出！")
            exit(0)
        self.data = pandas.DataFrame(list(self.collection.find()))
        try:
            self.data = self.data[['薪资', '工作经验', '学历要求', '职位', '公司地点']]
        except Exception as e:
            print(e)
            print("数据类型错误！\n退出！")
            return
        self.client.close()
        self.wish_data()
        self.create_path()
        self.save_sqlite = ToSql(self.keyword)

        self.view_area_top10_salary()
        self.view_area_top10_nums()
        self.view_job_top6_salary()
        self.view_job_top10_re()
        self.view_edu_salary_chart()
        self.view_experience_salary_chart()
        self.view_experience_edu_salary_chart()
        self.view_edu_proportion()
        self.view_salary_proportion()
        self.hot_city_map()
        self.view_word_cloud()

        # self.insert_db()
        # self.view_map()

    # 数据清洗
    def wish_data(self):
        self.data['薪资'] = self.data['薪资'].apply(self.wish_data_salary)
        self.data = self.data[self.data['薪资'] < 500000]
        self.data = self.data[self.data['薪资'] > 2000]
        self.data['公司地点'] = self.data['公司地点'].str.split('-', expand=True)[
            0]
        self.data['公司地点'] = self.data['公司地点'].str.split('市', expand=True)[
            0]
        self.data['公司地点'] = self.data['公司地点'].str.split('省', expand=True)[
            0]

    @staticmethod
    def wish_data_salary(salary):
        # 统一薪资单位为元/月，区间取中值，大部分薪资单位为万/月，先判断可减少判断次数
        if '万/月' in salary or '万以上/月' in salary or '万以下/月' in salary:
            if '-' in salary.split('万')[0]:
                return (float(salary.split('万')[0].split('-')[0]) + float(
                    salary.split('万')[0].split('-')[1])) / 2 * 10000
            else:
                return float(salary.split('万')[0]) * 10000
        elif '千/月' in salary or '千以上/月' in salary or '千以下/月' in salary:
            if '-' in salary.split('千')[0]:
                return (float(salary.split('千')[0].split('-')[0]) + float(
                    salary.split('千')[0].split('-')[1])) / 2 * 1000
            else:
                return float(salary.split('千')[0]) * 1000
        elif '万/年' in salary or '万以上/年' in salary or '万以下/年' in salary:
            if '-' in salary.split('万')[0]:
                return (float(salary.split('万')[0].split('-')[0]) + float(
                    salary.split('万')[0].split('-')[1])) / 2 * 10000 / 12
            else:
                return float(salary.split('万')[0]) * 10000 / 12
        elif '元/天' in salary or '元以上/天' in salary or '元以下/天' in salary:
            if '-' in salary.split('元')[0]:
                return (float(salary.split('元')[0].split('-')[0]) + float(
                    salary.split('元')[0].split('-')[1])) / 2 * 30.5
            else:
                return float(salary.split('元')[0]) * 30.5

    @staticmethod
    def view_map():
        client = MongoClient()
        collection = client['Job51']['汇总']
        data = pandas.DataFrame(list(collection.find()))
        client.close()
        attr = data['_id'].tolist()
        data['平均薪资'] = data['平均薪资'].apply(lambda x: '%.0f' % x)
        v1 = data['职位数'].tolist()
        v2 = data['平均薪资'].tolist()
        bar = pyecharts.Bar("常见语言对比")
        bar.add("职位数", attr, v1, mark_point=["min", "max"])
        bar.add("平均薪资", attr, v2, mark_point=["min", "max"],
                mark_line=["average"])
        bar.render('static/html/master.html')

    def insert_db(self):
        client = MongoClient()
        collection = client['Job51']['汇总']
        avg = self.data['薪资'].mean()

        try:
            collection.insert_one({
                '_id': self.keyword,
                '职位': self.keyword,
                '平均薪资': avg,
                '职位数': self.get_count()
            })
        except Exception as e:
            _ = e
            collection.update_one(
                {'_id': self.keyword},
                {'$set': {'平均薪资': avg,
                          '职位数': self.get_count()}
                 })
        finally:
			print(list(collection.find()))
			client.close()

    def view_word_cloud(self):
        mask = plt.imread("static/img/background.jpg")
        name_list = self.data['职位'].tolist()
        text = ''.join(name_list)
        txt = ' '.join(jieba.cut(text))
        cloud = WordCloud(background_color='white', width=1000, height=700,
                          font_path='SIMLI.TTF',
                          mask=mask).generate(txt)
        plt.figure(dpi=200, figsize=(9, 6))
        plt.imshow(cloud, interpolation='bilinear')
        plt.axis('off')
        plt.savefig(
            'static/img/view_picture/' + self.keyword + '_WordCloud.jpg')

    def view_edu_salary_chart(self):
        # 根据学历排序
        edu = self.data.groupby('学历要求').mean().sort_values(by='学历要求',
                                                           ascending=True)
        x_axis = edu['薪资'].index.values
        y_axis = edu['薪资'].values

        try:
            edu = [x_axis[2], x_axis[0], x_axis[7], x_axis[4], x_axis[5],
                   x_axis[6], x_axis[3]]
            salary = [int(y_axis[2]), int(y_axis[0]), int(y_axis[7]),
                      int(y_axis[4]), int(y_axis[5]),
                      int(y_axis[6]), int(y_axis[3])]
        except Exception as e:
            _ = e
            try:
                edu = [x_axis[2], x_axis[0], x_axis[4], x_axis[5],
                       x_axis[6],
                       x_axis[3]]
                salary = [int(y_axis[2]), int(y_axis[0]), int(y_axis[4]),
                          int(y_axis[5]),
                          int(y_axis[6]), int(y_axis[3])]
            except Exception as e:
                _ = e
                try:
                    edu = [x_axis[2], x_axis[0], x_axis[4], x_axis[5],
                           x_axis[3]]
                    salary = [int(y_axis[2]), int(y_axis[0]),
                              int(y_axis[4]),
                              int(y_axis[5]),
                              int(y_axis[3])]
                except Exception as e:
                    _ = e
                    edu = [x_axis[2], x_axis[0], x_axis[4], x_axis[3]]
                    salary = [int(y_axis[2]), int(y_axis[0]),
                              int(y_axis[4]),
                              int(y_axis[3])]

            # 绘制柱状图
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.figure(dpi=200, figsize=(9, 6))
        plt.bar(edu, salary, width=0.7, color=self.get_color())
        for x, y in zip(edu, salary):
            plt.text(x, y, y, ha='center', va='bottom')
        plt.title(self.keyword + '相关职位学历与平均薪资关系', fontsize=16)
        plt.xlabel('学历', fontsize=12)
        plt.ylabel('平均薪资（元/月）', fontsize=12)
        plt.savefig(
            "static/img/view_picture/" + self.keyword + '_edu_salary_chart.png')

    # 根据经验求对应的平均薪资
    def view_experience_salary_chart(self):
        # 根据经验排序
        experience = self.data.groupby('工作经验').mean().sort_values(
            by='工作经验',
            ascending=True)
        x_axis = experience['薪资'].index.values
        y_axis = experience['薪资'].values
        experience = [x_axis[6], x_axis[1], x_axis[2], x_axis[3],
                      x_axis[4],
                      x_axis[5], x_axis[0]]
        salary = [int(y_axis[6]), int(y_axis[1]), int(y_axis[2]),
                  int(y_axis[3]), int(y_axis[4]), int(y_axis[5]),
                  int(y_axis[0])]

        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.figure(dpi=200, figsize=(9, 6))
        plt.bar(experience, salary, width=0.7, color=self.get_color())
        for x, y in zip(experience, salary, ):
            plt.text(x, y, y, ha='center', va='bottom')

        plt.title(self.keyword + '相关职位经验与平均薪资关系', fontsize=16)
        plt.xlabel('经验', fontsize=12)
        plt.ylabel('平均薪资（元/月）', fontsize=12)
        plt.savefig(
            'static/img/view_picture/' + self.keyword + '_experience_salary_chart.png')

    def view_area_top10_nums(self):
        area = self.data[self.data['公司地点'] != '异地招聘'][
            '公司地点'].value_counts()
        city = list(area.index)[:10]
        nums = list(area.values)[:10]

        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.figure(dpi=200, figsize=(9, 6))
        plt.bar(city, nums, width=0.7, color=self.get_color())
        for x, y in zip(city, nums):
            plt.text(x, y, y, ha='center', va='bottom')

        plt.title('发布招聘信息（' + self.keyword + '）最多的城市Top10', fontsize=16)
        plt.xlabel('城市', fontsize=12)
        plt.ylabel('招聘信息（条）', fontsize=12)
        plt.savefig(
            'static/img/view_picture/' + self.keyword + '_area_top10_nums.png')

    def hot_city_map(self):
        area = self.data[self.data['公司地点'] != '异地招聘'][
            '公司地点'].value_counts()
        city = list(area.index)
        nums = list(area.values)
        geo = Geo(f"{self.keyword}在招热力图",
                  f"data from {self.keyword} 51job.com",
                  title_color="#fff", title_pos="left",
                  width=1000, height=600)
        geo.add("全国招聘地点热力图", city, nums, visual_range=[0, 1000],
                type='scatter',
                visual_text_color="#fff",
                symbol_size=15, is_visualmap=True,
                is_roam=True)  # type有scatter, effectScatter, heatmap三种模式
        geo.render(
            path=f"static/html/view_html/{self.keyword}_hot_map.html")

    def view_area_top10_salary(self):
        group_area = self.data[self.data['公司地点'] != '异地招聘'].groupby(
            '公司地点').mean().sort_values(by='薪资', ascending=False)
        salary = list(group_area['薪资'].index.values)[:10]
        city = list(group_area['薪资'].values)[:10]

        plt.figure(dpi=200, figsize=(9, 6))
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.bar(salary, city, width=0.7, color=self.get_color())
        for x, y in zip(salary, city):
            plt.text(x, y, int(y), ha='center', va='bottom')

        plt.title(self.keyword + '相关职位薪资最多的城市Top10', fontsize=16)
        plt.xlabel('职位', fontsize=12)
        plt.ylabel('平均薪资（元/月）', fontsize=12)
        plt.savefig(
            'static/img/view_picture/' + self.keyword + '_area_top10_salary.png')

    def view_job_top6_salary(self):
        group_job = self.data.groupby('职位').mean().sort_values(by='薪资',
                                                               ascending=False)
        salary = list(group_job['薪资'].index.values)[:6]
        job = list(group_job['薪资'].values)[:6]

        plt.figure(dpi=200, figsize=(9, 6))
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.bar(salary, job, width=0.7, color=self.get_color())
        for x, y in zip(salary, job):
            plt.text(x, y, int(y), ha='center', va='bottom')

        plt.title(self.keyword + '相关职位薪资最多Top6', fontsize=16)
        plt.xticks(rotation=10)  # 倾斜10度
        plt.xlabel('职位', fontsize=12)
        plt.ylabel('平均薪资（元/月）', fontsize=12)
        plt.savefig(
            'static/img/view_picture/' + self.keyword + '_job_top6_salary.png')

    def view_job_top10_re(self):
        job = self.data['职位'].value_counts()
        job_name_all = list(job.index)
        job_name = job_name_all[:10]
        count = list(job.values)[:10]
        plt.figure(dpi=200, figsize=(9, 6))
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.bar(job_name, count, width=0.7, color=self.get_color())
        for x, y in zip(job_name, count):
            plt.text(x, y, y, ha='center', va='bottom')
        plt.xticks(rotation=14)
        plt.title(self.keyword + '相关职位最多招聘Top10', fontsize=16)
        plt.ylabel('招聘单位（家）', fontsize=12)
        plt.savefig(
            'static/img/view_picture/' + self.keyword + '_job_top10_re.png')
        self.save_sqlite.write_to_sqlite(job_name_all[:50])  # 职位最多的前50保存

    def view_experience_edu_salary_chart(self):
        experience = self.data.groupby(['工作经验', '学历要求']).mean().sort_values(by='工作经验',
                                                                            ascending=True)
        x_axis = list(experience['薪资'].index.values)
        y_axis = list(experience['薪资'].values)
        experience_list = ['在校生/应届生', '1年经验', '2年经验', '3-4年经验', '5-7年经验', '8-9年经验',
                           '10年以上经验']

        index_ex_edu = 0
        count = -1
        ex1 = '10年以上经验'
        ex2 = ''
        salary = []
        # 大专,本科,硕士对应薪资列表
        list_1 = []
        list_2 = []
        list_3 = []
        for _ in x_axis:
            for edu in x_axis[index_ex_edu]:
                if edu not in {'在校生/应届生', '无需经验', '1年经验', '2年经验', '3-4年经验', '5-7年经验',
                               '8-9年经验', '10年以上经验'}:
                    count += 1
                else:
                    ex2 = edu
                if edu == '大专':
                    list_1.append(int(y_axis[count]))
                elif edu == '本科':
                    list_2.append(int(y_axis[count]))
                elif edu == '硕士':
                    list_3.append(int(y_axis[count]))

                # 缺失值处理
                if ex1 != ex2:
                    if len(list_2) > len(list_3):
                        list_3.append(int(0))
                    if len(list_2) > len(list_1):
                        list_1.append(int(0))
                    ex1 = ex2

            index_ex_edu += 1

        salary.append(
            [list_1[6], list_1[1], list_1[2], list_1[3], list_1[4], list_1[5], list_1[0]])
        salary.append(
            [list_2[6], list_2[1], list_2[2], list_2[3], list_2[4], list_2[5], list_2[0]])
        salary.append(
            [list_3[6], list_3[1], list_3[2], list_3[3], list_3[4], list_3[5], list_3[0]])

        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.figure(dpi=200, figsize=(9, 6))
        xx = np.arange(7) - 0.3

        plt.bar(xx, salary[0], alpha=0.9, width=0.3, label='大专', fc='y', lw=1)
        for x, y in zip(xx, salary[0], ):
            plt.text(x, y, y, ha='center', va='bottom')

        plt.bar(xx + 0.3, salary[1], alpha=0.9, width=0.3, label='本科',
                tick_label=experience_list, fc='b', lw=1)
        for x, y in zip(xx, salary[1], ):
            plt.text(x + 0.3, y, y, ha='center', va='bottom')

        plt.bar(xx + 0.6, salary[2], alpha=0.9, width=0.3, label='硕士', fc='r', lw=1)
        for x, y in zip(xx, salary[2], ):
            plt.text(x + 0.6, y, y, ha='center', va='bottom')

        plt.title(self.keyword + '相关职位学历、经验与薪资的关系', fontsize=16)
        plt.xlabel('经验', fontsize=12)
        plt.ylabel('平均薪资（元/月）', fontsize=12)
        plt.legend(loc="upper left")
        # plt.rc('axes', unicode_minus=False)  # 解决 UserWarning: Glyph 8722
        plt.savefig(
            'static/img/view_picture/' + self.keyword + '_experience_edu_salary_chart.png')

    def view_edu_proportion(self):
        edu = self.data['学历要求'].value_counts()
        level = ['初中及以下', '中专', '高中', '大专', '本科', '硕士', '博士']
        level_start = level[::]
        nums = []
        for value in level_start:  # 未发现的学历要求删除
            try:
                nums.append(edu[value])
            except Exception as e:
                _ = e
                level.remove(value)
        # html样式饼图
        pie = Pie(self.keyword + '相关职位的学历分布', title_pos='center')
        pie.add(" ", level, nums, radius=[40, 75], is_label_show=True,
                legend_orient="vertical", legend_pos="right", width=10000,
                height=600, )
        pie.render(
            'static/html/view_html/' + self.keyword + '_edu_proportion.html')

    def view_salary_proportion(self):
        salary = self.data['薪资']
        level = ['5K及以下', '5K-10K', '10K-15K', '15K-20K', '20K-25K',
                 '25K-30K', '30K-35K', '35K-50K', '50K以上']
        nums = [0] * 9
        for value in salary.values:
            if 10000 < value <= 15000:
                nums[2] += 1
            elif 5000 < value <= 10000:
                nums[1] += 1
            elif value <= 5000:
                nums[0] += 1
            elif 15000 < value <= 20000:
                nums[3] += 1
            elif 20000 < value <= 25000:
                nums[4] += 1
            elif 25000 < value <= 30000:
                nums[5] += 1
            elif 30000 < value <= 35000:
                nums[6] += 1
            elif 35000 < value <= 50000:
                nums[7] += 1
            else:
                nums[8] += 1

        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.figure(figsize=(9, 6), dpi=200)
        plt.pie(nums, pctdistance=0.9, radius=1.2,
                explode=[0, 0, 0, 0, 0, 0.2, 0.3, 0.4, 0.5],
                autopct='%.2f%%', colors=self.get_color())
        plt.legend(level, bbox_to_anchor=(1.0, 1.0))
        plt.title(self.keyword + '相关职位的薪酬分布', fontsize=16)
        plt.savefig(
            'static/img/view_picture/' + self.keyword + '_salary_proportion.png')

    @staticmethod
    def create_path():
        if not os.path.exists(r'static/img/view_picture/'):
            os.makedirs(r'static/img/view_picture/')

    @staticmethod
    def get_color():
        colors = ['#00bcd4', '#0075d4', '#00d423', '#ffeb3b', '#795716',
                  '#792016', '#ab1705', '#5cd660', '#a45cd6',
                  '#009688']
        random.shuffle(colors)
        return colors

    def close_db(self):
        self.client.close()

    def get_count(self):
        return self.collection.estimated_document_count()


class ToSql(object):
    def __init__(self, keyword):
        self.keyword = keyword
        self.data = set()
        self.conn = sqlite3.connect("database.sqlite")
        self.cur = self.conn.cursor()

    def set_keyword(self, keyword):
        self.keyword = keyword

    def write_to_sqlite(self, data):
        """数据库中job，Title唯一"""
        self.data = data
        try:
            self.cur.execute(
                f"insert into Title (title) values ('{self.keyword}')")
        except Exception as e:
            _ = e
        title_qs = self.cur.execute(
            f"select id from title where title.title=='{self.keyword}'")
        title_id = [_ for _ in title_qs][0][0]
        for job in self.data:
            try:
                self.cur.execute(
                    f"insert into Job(job, title_id) values('{job}','{title_id}')")
            except Exception as e:
                _ = e
        self.conn.commit()

    def __del__(self):
        self.conn.close()


if __name__ == '__main__':

    View("网络营销")
    # title_list = ["大数据", "Python", "C语言", "C#", "Java", "web前端", "PHP",
    #               "Javascript", "Go", "C++", "运维", "软件测试", "网络推广",
    #               "Python开发", "云计算", "网络营销", "PHP","Java开发"]
    # for title in title_list:
    #     View(title)
