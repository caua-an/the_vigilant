"""Interface: RobotUI."""
import copy
import ctypes
import ctypes.util
import random
import tkinter as tk
from .theme import BG, RED


HEAD_ROWS = (6, 10, 14, 16, 18, 20, 20, 22, 22, 24, 24, 24, 24, 24, 24, 22, 22, 20, 20, 18, 16, 14, 10, 6)

METALS = {
    'Zinco': ('#243b4b', '#7094a1', '#c1d5d7', '#a1bdc3'),
    'Prata': ('#343b49', '#858f9c', '#ebeff3', '#bdc7d1'),
    'Cobre': ('#50332e', '#9a5a43', '#f1c09d', '#ce8966'),
    'Bronze': ('#4a3826', '#8c6b41', '#ebd19c', '#bb9866'),
}

VISORS = {'Preto acinzentado': '#20272d', 'Azul-escuro': '#1c3443', 'Verde-escuro': '#18352d'}

EYES = {'Azul-claro': '#a8e5e5', 'Azul-escuro': '#507fc4', 'Verde-claro': '#a7e6b4', 'Rosa': '#f2b4cf', 'Roxo': '#c5a7ef'}

DEFAULT_COLORS = {'metal': 'Zinco', 'visor': 'Azul-escuro', 'eyes': 'Azul-claro'}

NORMAL_MESSAGES = ['Hora de voltar aos estudos!', 'Seu objetivo está esperando.', 'Vamos voltar ao foco!', 'Um passo de cada vez. Continue!']

ADULT_MESSAGES = ['Volta a estudar, @!#$%!', 'Foco nessa @!#$% de tarefa!', 'Nada de distração, @!#$%!']


def bubble_position(x, y, width, height, screen_width, screen_height):
    right = x + 144 + 8
    left = right if right + width <= screen_width else x - width - 8
    left = max(0, min(left, screen_width - width))
    top = y - height + 36 if y >= height - 36 else y + 108
    return left, max(0, min(top, screen_height - height))


def shape_window(window, rectangles):
    """Recorta a janela externa usando a extensão XShape do X11."""
    class Rectangle(ctypes.Structure):
        _fields_ = [('x', ctypes.c_short), ('y', ctypes.c_short),
                    ('width', ctypes.c_ushort), ('height', ctypes.c_ushort)]

    try:
        x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
        xext = ctypes.CDLL(ctypes.util.find_library('Xext'))
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint)]
        x11.XFree.argtypes = [ctypes.c_void_p]
        xext.XShapeCombineRectangles.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                                  ctypes.c_int, ctypes.c_int, ctypes.POINTER(Rectangle),
                                                  ctypes.c_int, ctypes.c_int, ctypes.c_int]
        display = x11.XOpenDisplay(None)
        if not display:
            return
        try:
            root, parent = ctypes.c_ulong(), ctypes.c_ulong()
            children, count = ctypes.c_void_p(), ctypes.c_uint()
            if not x11.XQueryTree(display, window.winfo_id(), ctypes.byref(root), ctypes.byref(parent), ctypes.byref(children), ctypes.byref(count)):
                return
            if children.value:
                x11.XFree(children)
            rows = (Rectangle * len(rectangles))(*(Rectangle(*rect) for rect in rectangles))
            xext.XShapeCombineRectangles(display, parent.value, 0, 0, 0, rows, len(rows), 0, 0)
        finally:
            x11.XCloseDisplay(display)
    except (OSError, AttributeError, TypeError):
        pass  # Sem XShape, a janela mantém seu formato retangular.


def shape_head(window):
    shape_window(window, [((24 - width) // 2 * 6, y * 6, width * 6, 6)
                          for y, width in enumerate(HEAD_ROWS)])


class RobotUI:
    """Desenho e interação da cabeça e do balão flutuantes."""
    def show_robot(self):
        self.robot = tk.Toplevel(self.root)
        self.robot.overrideredirect(True)
        self.robot.attributes('-topmost', True)
        position = self.data.get('robot_position')
        if not (isinstance(position, list) and len(position) == 2 and all(type(v) is int for v in position)):
            position = [self.root.winfo_screenwidth() - 160, self.root.winfo_screenheight() - 195]
        x = max(0, min(position[0], self.root.winfo_screenwidth() - 144))
        y = max(0, min(position[1], self.root.winfo_screenheight() - 144))
        self.robot.geometry(f'144x144+{x}+{y}')
        self.canvas = tk.Canvas(self.robot, width=144, height=144, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<ButtonPress-1>', self.robot_press)
        self.canvas.bind('<B1-Motion>', self.robot_move)
        self.canvas.bind('<ButtonRelease-1>', self.robot_release)
        self.draw_robot(False)
        self.robot.update_idletasks()
        shape_head(self.robot)

    def robot_press(self, event):
        self.drag_start = (event.x_root, event.y_root, self.robot.winfo_x(), self.robot.winfo_y())
        self.dragged = False

    def robot_move(self, event):
        start_x, start_y, window_x, window_y = self.drag_start
        dx, dy = event.x_root - start_x, event.y_root - start_y
        if abs(dx) + abs(dy) < 5 and not self.dragged:
            return
        self.dragged = True
        x = max(0, min(window_x + dx, self.root.winfo_screenwidth() - 144))
        y = max(0, min(window_y + dy, self.root.winfo_screenheight() - 144))
        self.robot.geometry(f'+{x}+{y}')
        if self.bubble:
            self.position_bubble(x, y)

    def robot_release(self, event):
        if self.dragged:
            self.robot.update_idletasks()
            data = copy.deepcopy(self.data)
            data['robot_position'] = [self.robot.winfo_x(), self.robot.winfo_y()]
            self.commit(data)
        else:
            self.root.deiconify()
            self.root.lift()

    def draw_robot(self, angry, canvas=None):
        c = canvas if canvas is not None else self.canvas
        c.delete('all')
        def pixel(x, y, color):
            c.create_rectangle(x * 6, y * 6, x * 6 + 6, y * 6 + 6, fill=color, outline='')

        settings = self.customization()
        edge_color, shadow, highlight, metal = METALS.get(settings.get('metal'), METALS['Zinco'])
        visor = VISORS.get(settings.get('visor'), VISORS['Azul-escuro'])
        eye = EYES.get(settings.get('eyes'), EYES['Azul-claro'])
        # Cabeça redonda em pixels, com contorno e poucos detalhes metálicos.
        for y, width in enumerate(HEAD_ROWS):
            start = (24 - width) // 2
            for x in range(start, start + width):
                edge = y in (0, 23) or x in (start, start + width - 1)
                color = edge_color if edge else shadow if y > 18 or x > 19 else highlight if y < 5 or x < 4 else metal
                pixel(x, y, color)
        for x, y in ((7, 3), (8, 3), (9, 3), (6, 4), (18, 19), (17, 20)):
            pixel(x, y, highlight if y < 10 else shadow)
        # Um visor amplo, integrado à carcaça, forma o rosto do robô.
        for y in range(6, 18):
            for x in range(4, 20):
                if (x in (4, 19) and y in (6, 17)):
                    continue
                pixel(x, y, edge_color if y in (6, 17) or x in (4, 19) else visor)
        color = RED if angry else eye
        for x in (8, 14):
            for y in (10, 11, 12):
                pixel(x, y, color)
                pixel(x + 1, y, color)
            pixel(x, 10, '#ffe0dc' if angry else '#e1ffff')
        if angry:
            for x, y in ((7, 8), (8, 9), (9, 9), (14, 9), (15, 9), (16, 8)):
                pixel(x, y, color)
            for x in range(10, 14):
                pixel(x, 14, color)
        else:
            for x, y in ((10, 14), (11, 15), (12, 15), (13, 14)):
                pixel(x, y, color)
        for x in (10, 11, 12, 13):
            pixel(x, 20, shadow)
        if canvas is not None:
            c.scale('all', 0, 0, 0.5, 0.5)

    def show_bubble(self):
        settings = self.customization()
        adult = settings.get('adult', False)
        messages = NORMAL_MESSAGES + (ADULT_MESSAGES if adult else [])
        messages += [item['text'] for item in settings.get('messages', []) if adult or not item['adult']]
        self.bubble_text = random.choice(messages)
        self.hide_bubble()
        self.bubble = tk.Toplevel(self.root)
        self.bubble.overrideredirect(True)
        self.bubble.attributes('-topmost', True)
        self.bubble_canvas = tk.Canvas(self.bubble, width=270, height=96, bg='#263b49', highlightthickness=0)
        self.bubble_canvas.pack()
        self.robot.update_idletasks()
        self.position_bubble(self.robot.winfo_x(), self.robot.winfo_y())

    def position_bubble(self, x, y):
        bx, by = bubble_position(x, y, 270, 96, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        self.bubble.geometry(f'270x96+{bx}+{by}')
        c = self.bubble_canvas
        c.delete('all')
        below = by > y
        tail = max(32, min(238, x + 72 - bx))
        body_y = 16 if below else 0
        # Faixas em degraus formam o balão e sua ponta, sem fundo retangular.
        body = [(16, body_y, 238, 4), (8, body_y + 4, 254, 4),
                (4, body_y + 8, 262, 56), (8, body_y + 64, 254, 4),
                (16, body_y + 68, 238, 4)]
        if below:
            tip = [(tail - 2, 0, 4, 4), (tail - 6, 4, 12, 4), (tail - 10, 8, 20, 4), (tail - 14, 12, 28, 4)]
        else:
            tip = [(tail - 14, 72, 28, 4), (tail - 10, 76, 20, 4), (tail - 6, 80, 12, 4), (tail - 2, 84, 4, 4)]
        for rx, ry, width, height in body + tip:
            c.create_rectangle(rx, ry, rx + width, ry + height, fill='#263b49', outline='')
        c.create_rectangle(12, body_y + 8, 258, body_y + 64, fill='#f5f7f2', outline='')
        c.create_rectangle(8, body_y + 16, 262, body_y + 56, fill='#f5f7f2', outline='')
        c.create_text(135, body_y + 36, text=self.bubble_text, width=234, fill='#172d3b', font=('DejaVu Sans Mono', 10, 'bold'), justify='center')
        self.bubble.update_idletasks()
        shape_window(self.bubble, body + tip)

    def hide_bubble(self):
        if self.bubble:
            self.bubble.destroy()
            self.bubble = None
