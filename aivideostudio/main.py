import sys
from aivideostudio.app import create_app

def main():
    app, window = create_app(sys.argv)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
