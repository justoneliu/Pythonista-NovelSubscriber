import re
from urllib.parse import urljoin
import appex
import ui
import requests
from bs4 import BeautifulSoup
import contacts


def read_contact(name='Novels', option='check'):
	"""
	name: str: a name in the Contacts
	option: str: 'check' means getting urls for checking update
				 'read' means getting urls for reading

	urls: list of str: urls of the novel page
	lastChapters: list of str: the last chapter you saw
	"""
	# 从通讯录找出"Novels"名片
	person = contacts.find(name)[0]
	# 读取小说的发布网址
	if option == 'check':
		urls = [url[1] for url in person.url]
	# 读取小说的阅读网址
	elif option == 'read':
		urls = [url[1] for url in person.email]
	# 读取小说的已阅章节数
	lastChapters = [lastChapter[1] for lastChapter in person.phone]
	return urls, lastChapters


def write_contact(newChapters, name='Novels'):
	"""update records of the last chapter you saw
	newChapters: list of str: the last chapter you saw
	name: str: a name in the Contacts
	"""
	person = contacts.find(name)[0]
	# 读取各小说标签
	catalog = [novel[0] for novel in person.phone]
	# 在 phone 属性写入各小说标签和相应的已阅章节数
	person.phone = [(n, c) for n, c in zip(catalog, newChapters)]
	contacts.save()


def cn2num(cnum):
	"""convert Chinses number to integer number
	cnum: str: Chinese number
	
	num: int: integer number
	"""
	num = 0
	weights = {'十': 10, '百': 100, '千': 1000}
	num_dict = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '零': 0}
	# 通过集合的交集判断章节数是否带权位
	if len(set(cnum) & set(weights.keys())):
		# 带权位的形式，零没有意义，去除零
		cnum = ''.join(cnum.split('零'))
		weight = 1
		for i in range(len(cnum)):
			item = cnum[-1-i]
			if item in weights.keys():
				weight = weights[item]
			else:
				num += num_dict[item] * weight
	else:
		# 无权位的形式
		num = int(''.join([str(num_dict[item]) for item in cnum]))
	return num


def download(url, ua=0, encoding='utf-8'):
	"""
	url: str: url of the novel page or reading page
	ua: int: indicate which user agent to use
	encoding: str: indicate the encoding to use for decoding the response
	
	html: str: the website page or the 'failed' string
	"""
	# 设置用户代理，分别是 iPhone Safari, Mac Chrome
	userAgents = ["Mozilla/5.0 (iPhone; CPU iPhone OS 12_1_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.109 Safari/537.36"]
	headers = {'User-Agent': userAgents[ua]}
	# 发送 HTTP 请求
	r = requests.get(url, headers=headers)
	# 指示网页的编码类型
	r.encoding = encoding
	html = r.text if r.status_code == 200 else 'failed'
	return html


def extract(html, url=None, option='chapter'):
	"""
	html: str: website page or the 'failed' string
	url: str: url of the website page
	option: str: 'chapter' means to extract chapter number
							 'link' means to extract the update chapter number and links
							 'article' means to extract article of the update chapter
							 
	result: str: chapter number for 'chapter'
				 chapter information and links for 'link'
				 article for 'article'
	"""
	if html == 'failed':
		result = html
	else:
		soup = BeautifulSoup(html, 'html5lib')
		if option == 'chapter':
			# 提取章节信息
			if 'zongheng' in url:
				text = soup.find('span', {'class': 'last_tit'}).string
			else:
				text = soup.find('p', {'id': 'ariaMuLu'}).get_text()
			try:
				# 从章节信息提取章节数，中文数字形式
				result = re.search('第(.*?)章', text)[1]
			except TypeError:
				result = re.search('至(.*?)章', text)[1]
		elif option == 'link':
			# 提取最近章节信息和链接，并将相对链接转换成绝对链接
			start_url = 'https://www.biquge.com.cn'
			ul = soup.find('ul', {'class': 'chapter'})
			result = [(link.get_text(), urljoin(start_url, link.get('href'))) for link in ul.find_all('a')]
		elif option == 'article':
			# 提取正文
			result = soup.find('div', {'id': 'content'}).get_text()
	return result


def check():
	"""
	updatePrompt: str: update check result
	"""
	# 读取发布网址和已阅章节数
	urls, lastChapters = read_contact()
	# 抓取发布网址的最新章节数
	newChapters = [extract(download(url), url) for url in urls]
	# 对比最新章节数和已阅章节数
	updateNums = [cn2num(new) - int(last) for new, last in zip(newChapters, lastChapters)]
	# 描述更新情况
	updatePrompt = f"小说更新情况\r\n凡人修仙：{updateNums[0]}\r\n天下第九：{updateNums[1]}\r\n元尊：{updateNums[2]}"
	return updatePrompt


def get_article():
	"""
	articles: str: contents of update chapter
	"""
	articles = ''
	# 读取阅读网址和已阅章节数
	urls, lastChapters = read_contact(option='read')
	# 抓取最近章节信息和绝对链接
	recentURLs = [extract(download(url), option='link') for url in urls]
	# 判断出未阅章节，并下载页面，提取正文
	for rURLs, lastChapter, i in zip(recentURLs, lastChapters, range(3)):
		articles += '----小说分割线----\r\n'
		for chapter in reversed(rURLs):
			try:
				match = re.search('第(.*?)章', chapter[0])
				if match:
					chapterNum = cn2num(match[1])
				else:
					chapterNum = cn2num(chapter[0].split('章')[0])
				if chapterNum > int(lastChapter):
					article = extract(download(chapter[1], ua=1), option='article')
					articles += chapter[0] + '\r\n' + article + '\r\n\r\n'
					lastChapters[i] = str(chapterNum)
			except TypeError:
				print(f'{i},非正文章节')
	# 更新已阅章节数
	write_contact(lastChapters)
	return  articles


def read_action():
	view = ui.load_view('read.pyui')
	view.subviews[0].text = get_article()
	view.present()


def botton_tapped(sender):
	# 由于iOS的限制，Widget程序能申请的内存有限，经常无法展开无广告阅读界面，因此将无广告阅读放在Pythonista中执行
	pass


# 以 Widget 的形式运行，检测更新
if appex.is_widget():
	# 创建图层
	view = ui.View(
		frame=(0, 0, 380, 120),
		background_color=(0.0, 0.0, 0.0, 0.1))
	# 创建标签，用来展示更新状态
	label = ui.Label(
		frame=(44, 0, 236, 120),
		flex='TLWH',
		font=('<System>', 18),
		number_of_lines=5,
		text_color='black',
		text=check())
	# 将标签添加到图层
	view.add_subview(label)
	# 创建按钮，用来触发无广告阅读界面
	botton = ui.Button(
		frame=(336,40,40,40),
		action=botton_tapped,
		font=('<System>', 20),
		title='Read')
	# 将按钮添加到图层
	view.add_subview(botton)
	# 显示界面
	appex.set_widget_view(view)
# 在 Pythonista 中运行，无广告阅读小说
else:
	read_action()



