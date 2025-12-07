from ttkbootstrap import Window
from db import init_db
from ui import TaskerApp

def main():
    init_db()
    root = Window(themename="darkly")
    TaskerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
