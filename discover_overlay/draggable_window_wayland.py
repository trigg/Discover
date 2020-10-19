import gi
gi.require_version("Gtk", "3.0")
import cairo
from gi.repository import Gtk, Gdk, GtkLayerShell
import logging


class DraggableWindowWayland(Gtk.Window):
    def __init__(self, x=0, y=0, w=300, h=300, message="Message", settings=None):
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
        if w < 100:
            w = 100
        if h < 100:
            h = 100
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.settings=settings
        self.message = message
        self.set_size_request(50, 50)

        self.connect('draw', self.draw)
        self.connect('motion-notify-event', self.drag)
        self.connect('button-press-event', self.button_press)
        self.connect('button-release-event', self.button_release)

        self.set_app_paintable(True)
        self.monitor = 0

        self.drag_type = None
        self.drag_x = 0
        self.drag_y = 0
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)

        self.show_all()
        #self.force_location()

    def force_location(self):
        (sx, sy)= self.get_size()
        if self.x < 0:
            self.x=0
        if self.y < 0:
            self.y=0
        if self.x + self.w > sx:
            self.x = sx - self.w
        if self.y + self.h > sy:
            self.y = sy - self.h
        self.queue_draw()

    def drag(self, w, event):
        if event.state & Gdk.ModifierType.BUTTON1_MASK:
            if self.drag_type == 1:
                # Center is move
                self.x += event.x - self.drag_x
                self.y += event.y - self.drag_y
                self.drag_x = event.x
                self.drag_y = event.y

                self.force_location()
            elif self.drag_type == 2:
                # Right edge
                self.w += event.x - self.drag_x
                self.drag_x = event.x
                self.force_location()
            elif self.drag_type == 3:
                # Bottom edge
                self.h += event.y - self.drag_y
                self.drag_y = event.y
                self.force_location()
            else:
                # Bottom Right
                self.w += event.x - self.drag_x
                self.h += event.y - self.drag_y
                self.drag_x = event.x
                self.drag_y = event.y
                self.force_location()

    def button_press(self, w, event):
        px = event.x - self.x
        py = event.y - self.y

        if not self.drag_type:
            self.drag_type = 1
            # Where in the window did we press?
            if px < 20 and py<20:
                self.settings.change_placement(None)
            if py > self.h - 32:
                self.drag_type += 2
            if px > self.w - 32:
                self.drag_type += 1
            self.drag_x = event.x
            self.drag_y = event.y

    def button_release(self, w, event):
        self.drag_type = None

    def draw(self, widget, context):
        context.translate(self.x, self.y)
        context.save()
        context.rectangle(0,0,self.w,self.h)
        context.clip()

        context.set_source_rgba(1.0, 1.0, 0.0, 0.7)
        # Don't layer drawing over each other, always replace
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()
        # Get size of window

        # Draw text
        context.set_source_rgba(0.0, 0.0, 0.0, 1.0)
        xb, yb, w, h, dx, dy = context.text_extents(self.message)
        context.move_to(self.w / 2 - w / 2, self.h / 2 - h / 2)
        context.show_text(self.message)

        # Draw resizing edges
        context.set_source_rgba(0.0, 0.0, 1.0, 0.5)
        context.rectangle(self.w - 32, 0, 32, self.h)
        context.fill()

        context.rectangle(0, self.h - 32, self.w, 32)
        context.fill()

        # Draw Done!
        context.set_source_rgba(0.0, 1.0, 0.0, 0.5)
        context.rectangle(0, 0, 20,20)
        context.fill()
        context.restore()


    def get_coords(self):
        return (self.x,self.y,self.w,self.h)