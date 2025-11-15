import paramiko,linecache,json,requests,time,base64,redis
from io import StringIO

def get_config():
    config = json.loads(open("/root/jvmcheck.json", encoding='utf-8').read()) #读取配置文件，填写绝对路径
    return config

class redis_operate():
    def redis_set(text1,text2):     #radis写入
        redis_pool.set(text1, text2)
    def redis_get(text):        #redis读取
        return redis_pool.get(text)

def getjvm():
    try:
        # 实例化一个transport对象，填写IP和端口
        trans = paramiko.Transport((sshdata['ip'], int(sshdata['port'])))
        # 建立连接，输入用户名密码，密码使用base64解码
        trans.connect(username=sshdata['username'], password=base64.b64decode(sshdata['password']))
        # 将sshclient的对象的transport指定为以上的trans
        ssh = paramiko.SSHClient()
        ssh._transport = trans
        # 执行命令，和传统方法一样
        stdin, stdout, stderr = ssh.exec_command('jps')     #执行shell命令
        jps = StringIO(stdout.read().decode())
        startid = 0
        for line in jps:
            if "Start" in line:     #找到运行中的jvm进程ID
                startid = line.split()
        stdin, stdout, stderr = ssh.exec_command('jmap -heap ' + startid[0])    #执行shell命令
        jmaporiginal = stdout.read().decode()
        jmap = StringIO(jmaporiginal).readlines()
        # 关闭连接
        trans.close()
        NewGeneration = int(jmap[25].split()[2])
        concurrentmarksweepgeneration = int(jmap[45].split()[2])
        #print(NewGeneration)
        #print(concurrentmarksweepgeneration)
        used = NewGeneration + concurrentmarksweepgeneration    #计算使用的内存总量
        Usagerate = used / 34359738368  # JVM配置32G内存
        print(Usagerate)
        if Usagerate > 0.8:     #设置为超过80%报警
            if redis_operate.redis_get(sshdata['hostname']) != "NO":    #读取主机名命名的redis key
                Usagerate = '%.2f%%' % (Usagerate * 100)
                post_weixin(sshdata['hostname'] + " " + sshdata['ip'] + "\nJVM内存使用率为" + str(
                    Usagerate) + "，请立即处理。\n点击可查看日志")
                f = open(sshconfig['path'] + time.strftime('%Y%m%d', time.localtime()) + sshdata['hostname'] + ".txt",
                         'a')
                f.write("-------------------------------\n" + time.strftime('%Y-%m-%d %H:%M:%S',
                                                                            time.localtime()) + "\n" + jmaporiginal + "\n")
                print("发送告警")
                redis_operate.redis_set(sshdata['hostname'],"NO")   #写入主机名命名的redis key值
            else:
                print("告警已存在")
        else:
            if redis_operate.redis_get(sshdata['hostname']) != "YES":
                Usagerate = '%.2f%%' % (Usagerate * 100)
                post_weixin(sshdata['hostname'] + " " + sshdata['ip'] + "\nJVM内存使用率为" + str(
                    Usagerate) + "，已恢复正常。\n点击可查看日志")
                redis_operate.redis_set(sshdata['hostname'],"YES")
            else:
                print("告警已解除")

    except:
        print(sshdata['ip']+"主机连接失败")

def post_weixin(stats): #发送微信
    url = sshconfig['weixin']['url']
    body = {
        "msgtype": "news",
        "news": {
            "articles": [
                {
                    "title": sshconfig['weixin']['title'],
                    "description": stats,
                    "url": sshconfig['weixin']['url2']+time.strftime('%Y%m%d', time.localtime())+sshdata['hostname']+".txt",
                    "picurl": sshconfig['weixin']['picurl']
                }
            ]
        }}
    response = requests.post(url, json=body)
    print(response.text)
    print(response.status_code)

sshconfig = get_config()
#建立redis连接池
redis_pool = redis.Redis(connection_pool=redis.ConnectionPool(host=sshconfig['redis']['host'],
                                                                     port=sshconfig['redis']['port'],
                                                                     password=sshconfig['redis']['password'],
                                                                     decode_responses=sshconfig['redis']['decode']))
#开始依次执行json文件中的主机
for sshdata in sshconfig['data']:
    getjvm()
print("\n程序执行完成")
