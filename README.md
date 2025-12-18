# Telegram-forward-listener说明
***已知账号自己发送大量内容，会封号，并且浪费时间收集资源，机器人可以进行大批量的操作，并且不会封号，但是机器人的权限很低，不能读取别人频道的东西，但是正常账号可以读取转发给机器人，这样机器人就能看到了，机器人发送内容一般是不会被特别限制，不过也要注意并发数***
![原理解释](https://fastly.jsdelivr.net/gh/bucketio/img14@main/2025/12/18/1766056512893-ccef2eb7-2fad-47ac-904e-efefddeb5aec.png)


## 关于配置
### 服务器要求（推荐服务器商：@idcluv）
程序是python编写的，然后面对并发的场景其实不是很多，当然如果希望稳定一点，我们可以选择稍微贵一些的服务器
![服务器要求](https://fastly.jsdelivr.net/gh/bucketio/img14@main/2025/12/18/1766051597258-126203e4-be4d-45b3-b410-553fc04b6e4c.png)
*购买挑选的注意事项*
购买的时候尽可能的选择ubuntu系统，追求稳定，如果习惯windows系统，这个配置是不够的，起码会贵上两倍。
![服务区配置要求](https://fastly.jsdelivr.net/gh/bucketio/img9@main/2025/12/18/1766051840423-00fcd47e-b243-4389-969e-973f394317e0.png)
购买后，等待开通
![](https://fastly.jsdelivr.net/gh/bucketio/img18@main/2025/12/18/1766052078782-127b2344-bf1a-4f5e-b0ad-71e703e6c39b.png)记住以上四个信息
## 链接配置服务器
### 软件推荐
推荐使用Finalshell或者xshell，以finalshell为例：[Finalshell下载](https://jisou.fun/sites/195.html/)
按提示安装成功后，建立ssh链接服务
![](https://fastly.jsdelivr.net/gh/bucketio/img15@main/2025/12/18/1766052370827-cb572509-6c54-4a4b-b5ea-613ec2f51e4b.png)


进行配置并保存
![](https://fastly.jsdelivr.net/gh/bucketio/img18@main/2025/12/18/1766052447505-72b94344-39f5-4052-9a6f-4d9eaeb0c0f0.png)
## 推荐操作
对于小白，以及不是很熟悉linux系统的同学，可以进去，第一件事就是下载aapanel面板，使用下面命令进行更新下载aapanel


`URL=https://www.aapanel.com/script/install_7.0_en.sh && if [ -f /usr/bin/curl ];then curl -ksSO "$URL" ;else wget --no-check-certificate -O install_7.0_en.sh "$URL";fi;bash install_7.0_en.sh aapanel`


进行下载，一路上只需要一次回车，等待下载完成，通常下载完成时间在7-12分钟，耐心等待，结束后，屏幕上会出现如下消息


`Congratulations! Installed successfully!
aaPanel Internet Address: https://1xxx.4x.180.x6:1xx/c9xxxx3
aaPanel Internal Address: https://1xxx.4x.180.x6:1xx/c9xxxx3
username: spxxxx
password: xxxxxxx`
## 着手配置
### 打开浏览器
在浏览器中，输入宝塔的面板信息：aaPanel Internet Address: https://1xxx.4x.180.x6:1xx/c9xxxx3
![](https://fastly.jsdelivr.net/gh/bucketio/img1@main/2025/12/18/1766056971143-8dfc2b31-2543-4478-a793-de528d2b296c.png)
登录
![](https://fastly.jsdelivr.net/gh/bucketio/img1@main/2025/12/18/1766052997256-e9a69507-7534-455e-965c-7c958481d8a5.png)
成功进入后。我们需要图示的两个导航
![](https://fastly.jsdelivr.net/gh/bucketio/img2@main/2025/12/18/1766053093705-cd52e700-848f-493f-89ab-a388244916fa.png)
新建一个文件夹，方便管理
![](https://fastly.jsdelivr.net/gh/bucketio/img4@main/2025/12/18/1766056903565-ada11aa7-4870-4632-89b8-4e347f5cfef4.png)
上传咱们的项目
![](https://fastly.jsdelivr.net/gh/bucketio/img0@main/2025/12/18/1766053305807-8bba72f6-abb4-46a6-9da4-b160eaeca104.png)
解压后。cut出来，如图所示

![](https://fastly.jsdelivr.net/gh/bucketio/img1@main/2025/12/18/1766053395885-524f3604-f486-4f52-a381-04192b29d410.png)
### 编辑5.0.1配置

![](https://fastly.jsdelivr.net/gh/bucketio/img0@main/2025/12/18/1766053742255-fde6ddc1-08a9-4a81-bab4-d5fab4628c66.png)
配置好后，记住路径
进入终端
*cd  /www/wwwroot/telegram/5.1.0
python3 -m pip install -r requirements.txt
sudo apt install tmux
tmux new -s telegram
python3 telegram.py*
***即可进入界面，按着提示，输入账号，验证码，2FA即可登录（一定要配置好master_id)***、

![](https://fastly.jsdelivr.net/gh/bucketio/img15@main/2025/12/18/1766055452904-f05121f5-69d2-4a44-85b8-bc7e28ba5a17.png)
tmux配置好后直接ctrl+b 然后点D，即可推出配置下一个
***4.0以及1.0机器人配置同理，不会请询问AI***
配置好后即可在telegram客户端进行交互
![](https://fastly.jsdelivr.net/gh/bucketio/img10@main/2025/12/18/1766055468575-20cac739-4ab5-423d-89df-cf46c3773ac3.png)

![](https://fastly.jsdelivr.net/gh/bucketio/img18@main/2025/12/18/1766055479330-b0930919-d8ed-42f6-8687-97d88c395d57.png)

![](https://fastly.jsdelivr.net/gh/bucketio/img3@main/2025/12/18/1766055581939-a7d457fb-8cb7-4e47-a030-c0d7930ec299.png)


***注意事项***
1.尽可能使用干净的ip,来申请API_id  API_hash,监听的账号推荐使用一年及以上的老号或者会员号，使用时尽可能的配置ip选项，推荐使用家宽保障账号长久活动


2.登陆好后监听号后，尽量保证不要和程序一起使用一个账号，有概率被秒冻结（尤其是购买的账号）


3.机器人也不要配置到自己的主账号，有时机器人调用过多也会概率冻结主账号


4.4.本工具仅供学习和研究telegram的机制，本人不对任何使用此工具进行非法活动承担任何责任！
