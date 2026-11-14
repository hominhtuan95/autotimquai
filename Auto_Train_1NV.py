"""Auto Train Mil và Cổ Mộ — 1 nhân vật, bản thử nghiệm không kích hoạt.
Chỉ Windows; đọc ảnh cửa sổ đang hiển thị; không đọc bộ nhớ game.
"""
import ctypes
from ctypes import wintypes
import json
import random
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageGrab, ImageTk
import numpy as np

if sys.platform != 'win32':
    raise SystemExit('Ứng dụng này chỉ hỗ trợ Windows 10/11.')

u = ctypes.windll.user32
u.SetProcessDPIAware()
WM_KEYDOWN, WM_KEYUP, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x100, 0x101, 0x201, 0x202
VK = {'Tab': 0x09, 'Space': 0x20, **{str(i): 0x30+i for i in range(10)}}
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
CONFIG = Path.home() / 'AutoTrainMil1NV_config.json'

class RECT(ctypes.Structure):
    _fields_ = [('left',ctypes.c_long),('top',ctypes.c_long),('right',ctypes.c_long),('bottom',ctypes.c_long)]

class POINT(ctypes.Structure):
    _fields_ = [('x',ctypes.c_long),('y',ctypes.c_long)]

ENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
u.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
u.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
u.PostMessageW.restype = wintypes.BOOL

def windows():
    out = []
    def cb(hwnd, unused):
        if not u.IsWindowVisible(hwnd): return True
        n = u.GetWindowTextLengthW(hwnd)
        if not n: return True
        buf = ctypes.create_unicode_buffer(n+1)
        u.GetWindowTextW(hwnd, buf, n+1)
        name = buf.value.strip()
        if name and 'Auto Train Mil' not in name:
            out.append((f'{name[:42]} [HWND {int(hwnd)}]', int(hwnd)))
        return True
    callback = ENUMPROC(cb)
    u.EnumWindows(callback, 0)
    return out

def client_box(hwnd):
    r=RECT()
    if not u.IsWindow(hwnd) or not u.GetClientRect(hwnd, ctypes.byref(r)): return None
    p=POINT(0,0)
    if not u.ClientToScreen(hwnd, ctypes.byref(p)): return None
    w,h=r.right-r.left,r.bottom-r.top
    if w<150 or h<150: return None
    return (p.x,p.y,p.x+w,p.y+h)

def screenshot(hwnd):
    box=client_box(hwnd)
    if box is None or u.IsIconic(hwnd): return None
    try: return ImageGrab.grab(bbox=box, all_screens=True).convert('RGB')
    except Exception: return None

def key(hwnd, v):
    if not u.IsWindow(hwnd): return False
    # Lparam contains a basic scan code; some games ignore background messages.
    scan = u.MapVirtualKeyW(v,0)
    return bool(u.PostMessageW(hwnd,WM_KEYDOWN,v,1 | (scan<<16)) and
                u.PostMessageW(hwnd,WM_KEYUP,v,0xC0000001 | (scan<<16)))

def click(hwnd, x, y):
    box=client_box(hwnd)
    if not box: return False
    w,h=box[2]-box[0],box[3]-box[1]
    x=max(1,min(w-2,int(x))); y=max(1,min(h-2,int(y)))
    lp=(y<<16)|(x & 0xffff)
    return bool(u.PostMessageW(hwnd,WM_LBUTTONDOWN,1,lp) and u.PostMessageW(hwnd,WM_LBUTTONUP,0,lp))

class App:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title('Auto Train Mil và Cổ Mộ — 1 nhân vật')
        self.root.geometry('650x790')
        self.root.resizable(False,False)
        self.root.configure(bg='#e9f4ff')
        self.running=threading.Event()
        self.thread=None
        self.items={}
        self.hwnds={}
        self.load()
        self.build()
        self.root.protocol('WM_DELETE_WINDOW',self.close)

    def load(self):
        self.data={}
        try: self.data=json.loads(CONFIG.read_text(encoding='utf-8'))
        except (OSError,ValueError): pass

    def save(self):
        data={'enabled':{k:v.get() for k,v in self.checks.items()},
              'intervals':{k:v.get() for k,v in self.intervals.items()},
              'move':self.move.get()}
        try: CONFIG.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError: pass

    def build(self):
        if (ROOT/'header.png').exists():
            im=Image.open(ROOT/'header.png').convert('RGB')
            self.header=ImageTk.PhotoImage(im)
            tk.Label(self.root,image=self.header,bd=0).pack()
        else:
            tk.Label(self.root,text='Auto Train Mil và Cổ Mộ',font=('Segoe UI',19,'bold'),fg='#0758a5',bg='#e9f4ff').pack(pady=15)
        tk.Label(self.root,text='Zalo: TuanHo – 0398438721  |  BẢN 1 NHÂN VẬT • KHÔNG KEY',font=('Segoe UI',10,'bold'),fg='#0758a5',bg='#e9f4ff').pack(pady=3)
        frame=tk.LabelFrame(self.root,text='NHÂN VẬT 1',bg='white',fg='#0865ad',font=('Segoe UI',12,'bold'),padx=13,pady=10)
        frame.pack(fill='x',padx=14,pady=9)
        row=tk.Frame(frame,bg='white');row.pack(fill='x')
        self.window=tk.StringVar()
        self.combo=ttk.Combobox(row,textvariable=self.window,state='readonly',width=48)
        self.combo.pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='Làm mới',command=self.refresh).pack(side='left',padx=6)
        self.refresh()
        self.checks={};self.intervals={}
        left=['Tìm Quái','Nhặt Đồ','Skill 1','Skill 2','Skill 3','Skill 4']
        right=['Skill 5','Skill 6','Skill 7','Bay chỗ khác (8)','Bơm Máu (9)','Bơm Mana (0)']
        columns=tk.Frame(frame,bg='white');columns.pack(fill='x',pady=(10,4))
        for ci,labels in enumerate((left,right)):
            col=tk.Frame(columns,bg='white');col.grid(row=0,column=ci,sticky='nw',padx=(0,14) if ci==0 else (8,0))
            for i,label in enumerate(labels):
                name=label
                var=tk.BooleanVar(value=self.data.get('enabled',{}).get(name,True))
                self.checks[name]=var
                tk.Checkbutton(col,text=label,variable=var,bg='white',anchor='w',font=('Segoe UI',9),width=18 if ci==0 else 20).grid(row=i,column=0,sticky='w',pady=3)
                if name not in ('Tìm Quái','Nhặt Đồ'):
                    default='180' if name=='Bay chỗ khác (8)' else '2'
                    v=tk.StringVar(value=self.data.get('intervals',{}).get(name,default))
                    self.intervals[name]=v
                    tk.Entry(col,textvariable=v,width=6,justify='center',font=('Segoe UI',9)).grid(row=i,column=1,padx=(1,0))
        self.auto=tk.Button(frame,text='▶ BẬT AUTO',command=self.toggle,bg='#21a95e',fg='white',activebackground='#148349',font=('Segoe UI',12,'bold'),height=2)
        self.auto.pack(fill='x',pady=(10,0))
        area=tk.LabelFrame(self.root,text='LÙA QUÁI NGẪU NHIÊN A–H',bg='white',fg='#0865ad',font=('Segoe UI',10,'bold'),padx=12,pady=10)
        area.pack(fill='x',padx=14,pady=6)
        self.move=tk.BooleanVar(value=self.data.get('move',False))
        tk.Checkbutton(area,text='Bật lùa quái (click 2 giây/lần, đứng đánh 10 giây)',variable=self.move,bg='white').pack(anchor='w')
        tk.Label(area,text='8 điểm A–H theo ảnh đánh dấu; click theo tọa độ tương đối.',bg='white',fg='#155e92').pack(anchor='w',pady=3)
        tk.Label(area,text='20 chuỗi lùa quái: chọn ngẫu nhiên một chuỗi mỗi vòng.',bg='white',fg='#345',wraplength=590,justify='left').pack(anchor='w',pady=3)
        tk.Label(area,text='Kết thúc chuỗi: đứng đánh 10 giây, rồi chọn chuỗi khác.',bg='white',fg='#345').pack(anchor='w')
        self.status=tk.StringVar(value='Chưa chạy. Chọn cửa sổ game rồi nhấn BẬT AUTO.')
        tk.Label(self.root,textvariable=self.status,bg='#e9f4ff',fg='#12446a',wraplength=610,justify='left',font=('Segoe UI',9)).pack(padx=16,pady=10,anchor='w')
        tk.Label(self.root,text='Tab: 3,5s  •  Nhặt Đồ: Space 0,1s (ẩn)  •  Bay: 180s',bg='#e9f4ff',fg='#42627c').pack(pady=3)
        tk.Label(self.root,text='Chạy thử tại bãi an toàn: nhấp chuột có thể ngắt đánh và làm nhân vật đi xa.',bg='#e9f4ff',fg='#9a5021',wraplength=610).pack(pady=2)

    def refresh(self):
        opts=windows();self.hwnds=dict(opts)
        self.combo['values']=list(self.hwnds)
        if opts: self.window.set(opts[0][0])

    def hwnd(self):return self.hwnds.get(self.window.get())

    def toggle(self):
        if self.running.is_set():
            self.running.clear();self.auto.config(text='▶ BẬT AUTO',bg='#21a95e');self.status.set('Đã yêu cầu dừng Auto.');return
        hwnd=self.hwnd()
        if not hwnd or not u.IsWindow(hwnd):
            messagebox.showwarning('Thiếu cửa sổ','Chọn đúng cửa sổ game.');return
        intervals={}
        for name,var in self.intervals.items():
            try:
                value=float(var.get().replace(',','.'))
                if not 0.1<=value<=10800:raise ValueError()
            except ValueError:
                messagebox.showwarning('Sai thời gian',f'{name}: nhập số từ 0,1 đến 10800 giây.');return
            intervals[name]=value
        self.save()
        flags={k:v.get() for k,v in self.checks.items()}
        self.running.set();self.auto.config(text='■ TẮT AUTO',bg='#d44545')
        self.thread=threading.Thread(target=self.worker,args=(hwnd,flags,intervals,self.move.get()),daemon=True)
        self.thread.start()

    def report(self,msg):
        try:self.root.after(0,lambda:self.status.set(msg))
        except RuntimeError:pass

    def worker(self,hwnd,flags,intervals,moving):
        now=time.monotonic()
        next_due={name:now for name,enabled in flags.items() if enabled}
        # 8 điểm tham chiếu theo ảnh game 864 x 648 (tọa độ client).
        # Đây là điểm nhấp theo màn hình, không phải tọa độ thế giới.
        points={'A':(112/864,145/648), 'B':(778/864,139/648),
                'C':(138/864,527/648), 'D':(766/864,536/648),
                'E':(457/864,540/648), 'F':(432/864,135/648),
                'G':(112/864,351/648), 'H':(785/864,351/648)}
        patterns=[
            'BB DD CC AA','DD CC DD CC','EE DD BB HH','AA BB DD CC',
            'HH DD EE CC','GG AA FF BB','BB HH DD EE','CC GG AA FF',
            'FF BB HH DD','EE CC GG AA','DD EE CC GG','AA FF BB HH',
            'HH BB FF AA','CC EE DD HH','GG CC EE DD','BB DD EE CC',
            'FF AA GG CC','DD HH BB FF','EE GG CC AA','AA CC DD BB'
        ]
        # Mỗi mẫu có 8 chữ = 8 click, mỗi click cách 2 giây.
        # Sau click cuối chờ 10 giây đứng đánh, rồi chọn mẫu khác.
        sequence=random.choice(patterns).replace(' ','')
        index=0
        phase='moving'
        next_move=now+2.0
        self.report('Chuỗi lùa quái: '+' '.join(sequence[i:i+2] for i in range(0,len(sequence),2)))
        while self.running.is_set() and u.IsWindow(hwnd):
            now=time.monotonic()
            for name in list(next_due):
                period=3.5 if name=='Tìm Quái' else 0.1 if name=='Nhặt Đồ' else intervals[name]
                if now>=next_due[name]:
                    vk=VK['Tab'] if name=='Tìm Quái' else VK['Space'] if name=='Nhặt Đồ' else VK[name.split()[-1].strip('()')] if name.startswith(('Bay','Bơm')) else VK[name.split()[-1]]
                    key(hwnd,vk)
                    next_due[name]=now+period
            if moving and now>=next_move:
                if phase=='fighting':
                    sequence=random.choice(patterns).replace(' ','')
                    index=0
                    phase='moving'
                    self.report('Chuỗi tiếp theo: '+' '.join(sequence[i:i+2] for i in range(0,len(sequence),2)))
                if phase=='moving':
                    letter=sequence[index]
                    box=client_box(hwnd)
                    if box:
                        w,h=box[2]-box[0],box[3]-box[1]
                        px,py=points[letter]
                        ok=click(hwnd,w*px,h*py)
                        if not ok:
                            self.report('Không gửi được click vào game; kiểm tra cửa sổ.')
                    index+=1
                    if index>=len(sequence):
                        phase='fighting'
                        next_move=now+10.0
                        self.report('Đã lùa xong: đứng đánh 10 giây (không click di chuyển).')
                    else:
                        next_move=now+2.0
            time.sleep(0.02)
        self.running.clear()
        self.report('Auto đã dừng (hoặc cửa sổ game đã đóng).')
        try:self.root.after(0,lambda:self.auto.config(text='▶ BẬT AUTO',bg='#21a95e'))
        except RuntimeError:pass

    def close(self):
        self.running.clear();self.save();self.root.destroy()

if __name__=='__main__':
    App().root.mainloop()
