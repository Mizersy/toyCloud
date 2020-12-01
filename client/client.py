#!/usr/bin/python
# -*- coding: UTF-8 -*-
from socket import *
import time
import hashlib
import json
import struct
import threading
import pymysql
import os
import inspect
import ctypes
import sys
import re

#服务端IP地址和端口号
serverIP = '127.0.0.1'
serverPort = 10086
#客户端IP地址和端口号
clientIP = '127.0.0.1'
clientPort = 10008

state = 0
isOnline = 0

#接收报文
def Receive(s):
    rec = b''
    try:
        #接收报文长度信息
        rec = s.recv(4)
    except Exception:
        pass
    if rec == b'':
        return 0
    data_len = struct.unpack("i",rec)[0]
    strdata = b""
    #如果报文没接完则继续接收
    while data_len > 0:
        #若剩余报文长度大于1024，则直接接收长度为1024的报文
        if data_len > 1024:
            data = s.recv(1024)
            strdata += data
            data_len -= len(data)
        #若剩余长度小于1024，则接收全部剩余报文
        else:
            data = s.recv(data_len)
            strdata += data
            data_len -= len(data)
    #返回报文信息
    return json.loads(strdata)

#登录函数
def loginFunc():
    # 输入用户名和密码
    userName = input("Please enter your username: ")
    password1 = input("Please enter your password: ")
    return userName,password1

#注册函数
def signUpFunc():
    # 输入用户名和密码
    while True:
        userName = input("Please enter your username: ")
        password1 = input("Please enter your password: ")
        password2 = input("Please enter your password again: ")
        if password1 == password2:
            break
        #如果两次密码不同，需再次输入
        else:
            print("Different passwords!\n")
    return userName,password1

#发送报文
def sendJson(s,string):
    #发送数据长度
    head = struct.pack("i",len(string))
    s.send(head)
    #发送数据
    s.send(string.encode('utf-8'))

#发送心跳包
def sendHeart(s):
    global isOnline
    while True:
        if isOnline == 0:
            return
        #心跳包是值为-1的整数
        head = struct.pack("i",-1)
        try:
            s.send(head)
        #若发送失败，则服务端掉线
        except Exception:
            print("The server is Offline.\n")
            sys.exit(1)
            #return
        time.sleep(3)
    pass

#声明资源
def declare(s,userName,filename,filepath,note):
    send_list = ["declare",userName,filename,note]
    sendJson(s,json.dumps(send_list))

#进度条显示
def process_bar(precent, width=50):
    use_num = int(precent*width)
    space_num = int(width-use_num)
    precent = precent*100
    #   第一个和最后一个一样梯形显示, 中间两个正确,但是在python2中报错
    #
    # print('[%s%s]%d%%'%(use_num*'#', space_num*' ',precent))
    # print('[%s%s]%d%%'%(use_num*'#', space_num*' ',precent), end='\r')
    print('[%s%s]%d%%'%(use_num*'#', space_num*' ',precent),file=sys.stdout,flush=True, end='\r')
    # print('[%s%s]%d%%'%(use_num*'#', space_num*' ',precent),file=sys.stdout,flush=True)

#用于接收包
def getSocket(s):
    global state
    global isOnline
    while True:
        if isOnline == 0:
            return
        #接收报文
        message = Receive(s)
        if message == 0:
            continue
        #声明资源的返回信息
        if message[0] == "declrep":
            if message[1] == 1:
                print("Declare file successfully!\n")
            else:
                print("Declare file failed!\n")
            state = 1
        
        #查看资源的返回信息
        if message[0] == "listrep":
            if message[1] == 0:
                print("Sorry,can't show the list.\n")
            else:
                #显示资源列表
                print("%15s\t%10s\t%10s\t%40s\t%10s\t" %("filename","username","state","md5","note"))
                for line in message[2]:
                    if len(line) == 5:
                        print("%15s\t%10s\t%10d\t%40s\t%10s\t" %(line[0],line[1],line[2],line[3],line[4]))
                    else:
                        print("%15s\t%10s\t%10d\t%40s\t" %(line[0],line[1],line[2],line[3]))
            state = 1

        #下载资源的返回信息
        if message[0] == "sourcerep":
            if message[1] == 0:
                print("Sorry,can't show the list.\n")
            else:
                #显示拥有所需资源的设备列表
                print("%15s\t%10s\t%20s\t%10s" %("filename","username","IP","Port"))
                #print(message[2])
                for line in message[2]:
                    print("%15s\t%10s\t%20s\t%10d" %(line[0],line[1],line[2],line[3]))
            state = 2
        
        #退出请求的返回信息
        if message[0] == "exitrep":
            if message[1] == 0:
                print("Sorry,exit failed.")
                state = 1
            else:
                print("exit successfully.")
                state = 3

HOST = 'localhost'
PORT = 1307
BUFFER_SIZE = 1024
HEAD_STRUCT = '128sIq32s'
info_size = struct.calcsize(HEAD_STRUCT)

#读取为md5
def cal_md5(file_path):
    with open(file_path, 'rb') as fr:
        md5 = hashlib.md5()
        md5.update(fr.read())
        md5 = md5.hexdigest()
        return md5

#获取文件信息
def get_file_info(filename):
    mydb = pymysql.connect("localhost","root","root","client")
    c = mydb.cursor()
    try:
        #在数据库中查找文件所在路径
        c.execute("select filepath from file where filename = '%s'" %filename)
        file_path = c.fetchall()[0][0]
    except:
        pass
    file_name = os.path.basename(file_path)
    file_name_len = len(file_name)
    file_size = os.path.getsize(file_path)
    md5 = cal_md5(file_path)
    #print(file_name)
    return file_path,file_name, file_name_len, file_size, md5

#发送文件
def send_file(socket_file_sender,filename):

    file_path,file_name, file_name_len, file_size, md5 = get_file_info(filename)
    file_head = struct.pack(HEAD_STRUCT, file_name.encode("utf-8"), file_name_len, file_size, md5.encode("utf-8"))

    #发送文件长度等相关信息
    socket_file_sender.send(file_head)
    sent_size = 0

    #读取并发送文件内容
    with open(file_path,"rb") as fr:
        while sent_size < file_size:
            remained_size = file_size - sent_size
            send_size = BUFFER_SIZE if remained_size > BUFFER_SIZE else remained_size
            send_file = fr.read(send_size)
            sent_size += send_size
            socket_file_sender.send(send_file)
    socket_file_sender.close()

#处理获取资源的请求
def dealConn(socket_file_sender,addr):
    #获取文件名
    filename = bytes.decode(socket_file_sender.recv(1024))
    #发送所需文件
    send_file(socket_file_sender,filename)

#发送文件的线程
def fileSender():
    # 创建TCP套接字，使用IPv4协议
    serverSocket = socket(AF_INET, SOCK_STREAM) 
    # 将TCP套接字绑定到指定端口
    serverSocket.bind((clientIP,clientPort)) 
    # 最大连接数为1
    serverSocket.listen(5) 
    global isOnline
    while True:
        #print("wait...\n")
        conn,addr = serverSocket.accept()
        if isOnline == 0:
            conn.close()
            continue
        thread = threading.Thread(target=dealConn, args=(conn, addr))
        thread.start()

#unpack文件信息
def unpack_file_info(file_info):
    file_name, file_name_len, file_size, md5 = struct.unpack(HEAD_STRUCT, file_info)
    file_name = file_name[:file_name_len]
    return file_name, file_size, md5

#登录状态
def online(s,userName):
    # 使用另一个线程去发心跳包
    global isOnline
    isOnline = 1
    thread = threading.Thread(target=sendHeart, args=(s,))
    getThread = threading.Thread(target=getSocket,args=(s,))
    
    thread.start()
    getThread.start()
    global state
    while True:
        #输入命令
        while True:
            #要求输入四种选项
            cmd = int(input("What do you want to do?\n\
                1.Declare a source.\n\
                2.See the sources list.\n\
                3.Download a source.\n\
                4.exit.\n"))
            if cmd >= 1 and cmd <= 4:
                break
        
        #Declare a source.
        if cmd == 1:
            #输入文件名和文件路径
            filename = input("Please input the filename:")
            filepath = input("Please input the file path:")
            path_store = filepath + "/" + filename
            #连接本地数据库
            mydb = pymysql.connect("localhost","root","root","client")
            c = mydb.cursor()
            #在本地数据库中存储文件名和文件路径
            c.execute("INSERT INTO file (filename,filepath) \
                    VALUES ('%s','%s')" %(filename,path_store))
            mydb.commit()
            mydb.close()
            #输入备注
            note = input("Please input the note:")
            declare(s,userName,filename,filepath,note)
            state = 0
        
        #See the sources list.
        elif cmd == 2:
            send_list = ["seelist"]
            #发送查看资源列表的请求
            sendJson(s,json.dumps(send_list))
            state = 0
        
        #Download a source.
        elif cmd == 3:
            #输入文件名
            filename = input("Please input the filename:")
            str_md5 = hashlib.md5(str.encode(filename)).hexdigest()
            send_list = ["seesource",str_md5]
            #发送下载资源的请求
            sendJson(s,json.dumps(send_list))
            state = 0
        
        #exit
        elif cmd == 4:
            send_list = ["exit",userName]
            #发送退出请求
            sendJson(s,json.dumps(send_list))
            state = 0
        while state == 0:
            pass

        #向另一个客户端请求资源
        if state == 2:
            #输入IP地址和端口号
            IP = input("Please input the IP address:")
            port = int(input("Please input the port:"))
            #建立socket连接
            socket_file_reveiver = socket(AF_INET, SOCK_STREAM) 
            socket_file_reveiver.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
            socket_file_reveiver.connect((IP,port))
            #发送文件名
            socket_file_reveiver.send(str.encode(filename))
            #接收文件信息
            file_info_package = socket_file_reveiver.recv(info_size)
            file_name, file_size, md5_recv_tmp = unpack_file_info(file_info_package)
            md5_recv = bytes.decode(md5_recv_tmp)

            #开始接收文件
            print("Start receive file %s" % bytes.decode(file_name))
            recved_size = 0
            #接收并写入文件
            with open(file_name, 'wb') as fw:
                while recved_size < file_size:
                    percent = recved_size / file_size
                    process_bar(percent)
                    remained_size = file_size - recved_size
                    recv_size = BUFFER_SIZE if remained_size > BUFFER_SIZE else remained_size
                    recv_file = socket_file_reveiver.recv(recv_size)
                    recved_size += recv_size
                    fw.write(recv_file)
            #判断接收是否正确
            md5 = cal_md5(bytes.decode(file_name))
            if md5 != md5_recv:
                print('\nMD5 compared fail!')
            else:
                print('\nReceived file %s successfully' % bytes.decode(file_name))
                filename = bytes.decode(file_name)
                filepath = os.getcwd()
                filepath = filepath.replace('\\','/')
                path_store = filepath + "/" + filename
                #连接数据库
                mydb = pymysql.connect("localhost","root","root","client")
                c = mydb.cursor()
                try:
                    #将该文件名及其本地路径存储在本地数据库中
                    c.execute("INSERT INTO file (filename,filepath) \
                            VALUES ('%s','%s')" %(filename,path_store))
                except Exception:
                    pass
                mydb.commit()
                mydb.close()
                note = ""
                #向服务器声明该资源
                declare(s,userName,filename,filepath,note)
                state = 0
                while state == 0:
                    pass
            socket_file_reveiver.close()
            pass
        if state == 3:
            isOnline = 0
            s.close()
            break

def main():
    #连接数据库
    mydb = pymysql.connect("localhost","root","root","client")
    c = mydb.cursor()
    try:
        #创建数据表
        c.execute('''CREATE TABLE file
        (filename char(50) not null,
        filepath char(100) not null,
        primary key(filename,filepath));''')
    except:
        pass
    mydb.commit()
    mydb.close()
    global isOnline
    isOnline = 0
    #创建发送文件的线程
    fileThread = threading.Thread(target=fileSender)
    fileThread.start()
    while True:
        # 创建TCP套接字，使用IPv4协议
        s = socket(AF_INET, SOCK_STREAM) 
        #s.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
        s.connect((serverIP,serverPort))
        loginOrSignup = input("Hello,what do you want to do?\n1.Log in.\n2.Sign up.\n3.exit\n")
        
        #登录
        if loginOrSignup == "1":
            #输入用户名和密码
            userName,password = loginFunc()
            #发送登录请求
            login_list = ["login",userName,password,clientIP,clientPort]
            sendJson(s,json.dumps(login_list))
            #接收登录响应
            message = Receive(s)
            if message[0] == "loginrep":
                #登录成功
                if message[1] == 1:
                    print("Login successful.\n")
                    online(s,userName)
                #用户名或密码错误
                elif message[1] == 0:
                    print("Sorry,wrong username or password.\n")
                    s.close()
                    continue
                #使用了其他设备的账户
                elif message[1] == 2:
                    print("Please enter your IP's account.")
                    s.close()
                    continue
        #注册
        elif loginOrSignup == "2":
            #输入用户名和密码
            userName,password = signUpFunc()
            #发送注册请求
            signUp_list = ["register",userName,password,clientPort]
            sendJson(s,json.dumps(signUp_list))
            #等待服务器响应
            print("Please wait a second...\n")
            message = Receive(s)

            #处理注册响应
            if message[0] == "regrep":
                #注册成功
                if message[1] == 1:
                    print("Sign up successfully!\n")
                    s.close()
                    continue
                #服务端拒绝请求
                elif message[1] == 0:
                    print("Sign up request denied.\n")
                    s.close()
                    continue
                #用户名已存在
                else:
                    print("The user name already exist.")
        #退出系统
        elif loginOrSignup == "3":
            s.close()
            break
    pass


if __name__ == '__main__':
    main()