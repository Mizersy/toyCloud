# -*- coding: UTF-8 -*-
#!/usr/bin/python
from socket import *
import time
import threading
import json
import hashlib
import struct
import traceback
import pymysql

serverIP = '127.0.0.1'
serverPort = 10086
BUFFER_SIZE = 1024

#发送json格式的报文
def sendJson(conn,string):
    #发送数据长度
    head = struct.pack("i",len(string))
    conn.send(head)
    #发送数据
    conn.send(string.encode('utf-8'))

#返回登录信息
def loginRep(conn,username,password,state):
    rep_list = ["loginrep",state]
    sendJson(conn,json.dumps(rep_list))

#返回注册信息
def registerRep(conn,perm):
    rep_list = ["regrep",perm]
    sendJson(conn,json.dumps(rep_list))

#返回声明资源的响应报文
def declareRep(conn,perm):
    rep_list = ["declrep",perm]
    sendJson(conn,json.dumps(rep_list))

#处理声明资源的请求
def declareSource(conn,username,filename,note):
    #文件名转md5编码
    str_md5 = hashlib.md5(str.encode(filename)).hexdigest()
    #连接数据库
    mydb = pymysql.connect("localhost","root","root","server")
    c = mydb.cursor()
    ret = 1
    try:
        #将资源信息插入数据库
        c.execute("INSERT INTO source (filename,username,state,md5,note) \
                VALUES ('%s','%s',1,'%s','%s')" %(filename,username,str_md5,note))
    except:
        ret = 0
    mydb.commit()
    mydb.close()
    return ret

#处理查看资源列表的请求
def listRep(conn):
    #连接数据库
    mydb = pymysql.connect("localhost","root","root","server")
    c = mydb.cursor()
    try:
        #从数据库中提取所有的资源信息
        c.execute("select filename,username,state,md5,note from source")
        sourcelist = c.fetchall()
        #成功时的响应报文
        send_list = ["listrep",1,sourcelist]
    except:
        #失败时的响应报文
        send_list = ["listrep",0]
    #返回查看资源列表的响应报文
    sendJson(conn,json.dumps(send_list))
    mydb.commit()
    mydb.close()

#处理查看拥有特定资源的设备列表的请求
def sourceRep(conn,str_md5):
    #连接数据库
    mydb = pymysql.connect("localhost","root","root","server")
    c = mydb.cursor()
    try:
        #选出拥有特定资源的设备
        c.execute("select S.filename,D.username,D.ip,D.port\
                    from source S,device D\
                    where S.username = D.username and S.state = 1 and S.md5 = '%s'" %str_md5)
        sourcelist = c.fetchall()
        #成功时的报文
        send_list = ["sourcerep",1,sourcelist]
    except:
        #失败时的报文
        send_list = ["sourcerep",0]
    #返回查看拥有特定资源的设备列表的响应报文
    sendJson(conn,json.dumps(send_list))
    mydb.commit()
    mydb.close()

#处理退出请求
def deviceExit(conn,username):
    #连接数据库
    mydb = pymysql.connect("localhost","root","root","server")
    c = mydb.cursor()
    try:
        #将设备在表中的状态置为0
        c.execute("update device set state = 0\
            where username = '%s'" %username)
        c.execute("update source set state = 0\
            where username = '%s'" %username)
        send_list = ["exitrep",1]
    except:
        send_list = ["exitrep",0]
    #返回退出请求响应
    sendJson(conn,json.dumps(send_list))
    mydb.commit()
    mydb.close()

#接收报文
def Receive(conn,username,online):
    if online == 1:
        #设置定时器
        conn.settimeout(5.0)
    else:
        conn.settimeout(None)
    rec = b''
    try:
        rec = conn.recv(4)
    #如果超时
    except timeout:
        print("%s lose connection.\n" %username)
        #连接数据库
        mydb = pymysql.connect("localhost","root","root","server")
        c = mydb.cursor()
        try:
            #将设备在数据库中的信息置为0
            c.execute("update device set state = 0 where username = '%s'" %username)
            c.execute("update source set state = 0 where username = '%s'" %username)
        except:
            traceback.print_exc()
        mydb.commit()
        mydb.close()
        return -1
    #处理连接断开
    except ConnectionResetError:
        print("%s lose connection.\n" %username)
        if online == 1:
            #连接数据库
            mydb = pymysql.connect("localhost","root","root","server")
            c = mydb.cursor()
            try:
                #将设备在数据库中的信息置为0
                c.execute("update device set state = 0 where username = '%s'" %username)
                c.execute("update source set state = 0 where username = '%s'" %username)
            except:
                traceback.print_exc()
            mydb.commit()
            mydb.close()
        return -1

    if rec == b'':
        #print("rec == none")
        return 0
    data_len = struct.unpack("i",rec)[0]
    #如果为心跳包，则不做处理
    if data_len < 0:
        return 0
    strdata = b""
    #若未接收完成，则继续接收
    while data_len > 0:
        #如果剩余长度大于1024，则直接接收长度为1024的报文
        if data_len > 1024:
            data = conn.recv(1024)
            strdata += data
            data_len -= len(data)
        #若剩余长度小于1024，则接收剩余长度的报文
        else:
            data = conn.recv(data_len)
            strdata += data
            data_len -= len(data)
    #返回接收到的报文
    return json.loads(strdata)

#处理客户端请求
def dealConn(conn,addr):
    online = 0
    username = ""
    while True:
        #接收报文段
        message = Receive(conn,username,online)
        if message == 0:
            #print("message == 0\n")
            continue
        if message == -1:
            break

        #处理登录请求
        if message[0] == "login":
            username = message[1]
            password = message[2]
            clientIP = message[3]
            clientPort = message[4]

            #连接数据库
            mydb = pymysql.connect("localhost","root","root","server")
            c = mydb.cursor()
            
            #判断是否使用了其他设备的账户
            c.execute("select count(*) from device \
                where username = '%s' and password = '%s' and (ip != '%s' or port != %d)" %(username,password,clientIP,clientPort))
            if c.fetchone()[0] > 0:
                loginRep(conn,username,password,2)
                continue

            #在数据库中进行查找
            c.execute("select count(*) from device \
                where username = '%s' and password = '%s'" %(username,password))
            mydb.commit()

            #判断用户名和密码是否正确
            if c.fetchone()[0] > 0:

                #将该设备在表中的状态置为1
                c.execute("update device set state = 1\
                    where username = '%s'" %username)
                c.execute("update source set state = 1\
                    where username = '%s'" %username)

                #设备状态为在线
                online = 1

                #返回登录成功响应
                loginRep(conn,username,password,1)
                print("%s is online,its IP address is %s." %(username,addr[0]))
                mydb.commit()
            else:
                #返回登录失败响应
                loginRep(conn,username,password,0)
                print("Refused login request from %s." %addr[0])
            mydb.close()

        #处理注册请求
        elif message[0] == "register":
            #连接数据库
            mydb = pymysql.connect("localhost","root","root","server")
            c = mydb.cursor()

            #判断用户名是否已存在
            c.execute("select count(*) from device \
                where username = '%s'" %message[1])
            mydb.commit()
            if c.fetchone()[0] > 0:
                registerRep(conn,-1)
                continue
            mydb.close()

            #人工选择是否允许其注册
            while True:
                perm = input("Do you want him sign up ? y/n\n")
                if perm == "y" or perm == "n":
                    break

            #若允许注册
            if perm == "y":
                #连接数据库
                mydb = pymysql.connect("localhost","root","root","server")
                c = mydb.cursor()
                #在表中插入设备信息
                c.execute("INSERT INTO device (username,password,state,ip,port) \
                        VALUES ('%s','%s',0,'%s',%d)" %(message[1],message[2],addr[0],message[3]))
                mydb.commit()
                mydb.close()
                #返回注册成功的响应
                registerRep(conn,1)
                print("%s register as %s." %(addr[0],message[1]))
            #若拒绝注册请求
            if perm == "n":
                #返回注册失败的响应
                registerRep(conn,0)
                print("Refused register request from %s." %addr[0])
        
        #处理声明资源请求
        elif message[0] == "declare":
            #声明资源
            ret = declareSource(conn,username,message[2],message[3])
            if ret == 1:
                print("%s declare a file %s." %(username,message[2]))
            #返回声明资源响应
            declareRep(conn,ret)
        
        #若为查看资源请求
        elif message[0] == "seelist":
            #处理查看资源请求
            listRep(conn)
        #若为查看拥有特定资源的设备列表的请求
        elif message[0] == "seesource":
            #处理查看拥有特定资源的设备列表的请求
            sourceRep(conn,message[1])
        #若为退出请求
        elif message[0] == "exit":
            #处理退出请求
            deviceExit(conn,message[1])
            online = 0



def main():

    #连接数据库
    mydb = pymysql.connect("localhost","root","root","server")
    c = mydb.cursor()
    try:
        #创建device表
        c.execute('''CREATE TABLE device
        (username char(50) primary key not null,
        password char(50) not null,
        state int not null,
        ip char(50) not null,
        port int not null);''')
    except:
        pass
    try:
        #创建source表
        c.execute('''CREATE TABLE source
        (filename char(50) not null,
        username char(50) not null,
        state int not null,
        md5 char(50) not null,
        note char(50),
        primary key(filename,username));''')
    except:
        pass
    mydb.commit()
    mydb.close()
    # 创建TCP套接字，使用IPv4协议
    serverSocket = socket(AF_INET, SOCK_STREAM) 
    # 将TCP套接字绑定到指定端口
    serverSocket.bind((serverIP,serverPort)) 
    # 最大连接数为1
    serverSocket.listen(5) 
    print("The server is ready to receive...")

    while True:
		# 接收到客户连接请求后，建立新的TCP连接套接字
        conn, addr = serverSocket.accept()
        print('Accept new connection from %s:%s...' % addr)

		# 使用另一个线程去收发数据,这样服务端就可以继续接受其他客户端连接
        thread = threading.Thread(target=dealConn, args=(conn, addr))
        thread.start()

    pass

if __name__ == '__main__':
    main()