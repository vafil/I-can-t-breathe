from __future__ import annotations

import math
import pathlib
import random
import arcade

SCREEN_W = 960
SCREEN_H = 640
TITLE = "I Can't Breathe"

 # пути к папкам
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"

 # числа для игры
PLAYER_SPEED = 5
ENEMY_SPEED = 120
OXY_DRAIN_PER_SEC = 6
OXY_HIT_LOSS = 18
LOW_OXY_THRESHOLD = 25
MAX_OXY = 100

 # состояния экрана
STATE_MENU = "menu"
STATE_PLAY = "play"
STATE_OVER = "over"
STATE_CLEAR = "clear"


class GameBase(arcade.Window):
    """база игры, тут без анимации и без эффектов"""

    def __init__(self) -> None:
        super().__init__(SCREEN_W, SCREEN_H, TITLE, update_rate=1 / 60)
        arcade.set_background_color(arcade.color.BLACK_OLIVE)

        # что сейчас происходит
        self.state = STATE_MENU
        self.lvl = 1
        self.lvl_max = 5
        self.oxy = MAX_OXY
        self.t_alive = 0.0
        self.anim_timer = 0.0

        # спрайты и физика
        self.p: arcade.Sprite | None = None
        self.phys: arcade.PhysicsEngineSimple | None = None

        self.walls = arcade.SpriteList()
        self.phys_walls = arcade.SpriteList()
        self.foes = arcade.SpriteList()
        self.oxy_pick = arcade.SpriteList()
        self.exits = arcade.SpriteList()
        self.emitters: list[arcade.Emitter] = []

        self.dead_played = False
        self.music_player: object | None = None

        # кнопки
        self.mv_l = False
        self.mv_r = False
        self.mv_u = False
        self.mv_d = False

        # камеры
        self.cam = arcade.Camera(self.width, self.height)
        self.cam_ui = arcade.Camera(self.width, self.height)

        # картинки
        self.player_tex = [
            arcade.load_texture(ASSETS / "models" / "player1.png"),
            arcade.load_texture(ASSETS / "models" / "player2.png"),
        ]
        self.enemy_tex = [
            arcade.load_texture(ASSETS / "models" / "enemy1.png"),
            arcade.load_texture(ASSETS / "models" / "enemy2.png"),
        ]

        # звуки
        self.s_pick = arcade.load_sound(ASSETS / "audio" / "pickup.wav")
        self.s_dead = arcade.load_sound(ASSETS / "audio" / "death.wav")
        self.s_music = arcade.load_sound(ASSETS / "audio" / "music.wav")
        self.s_start = arcade.load_sound(ASSETS / "audio" / "start.wav")


    def play_sound(self, snd: arcade.Sound | None, vol: float = 0.6, loop: bool = False):
        if snd:
            try:
                return snd.play(volume=vol, loop=loop)
            except Exception:
                return None
        return None

    def start_music(self) -> None:
        if self.s_music and not self.music_player:
            self.music_player = self.play_sound(self.s_music, vol=0.25, loop=True)

    def stop_music(self) -> None:
        try:
            if self.music_player and hasattr(self.music_player, "pause"):
                self.music_player.pause()
            if self.music_player and hasattr(self.music_player, "delete"):
                self.music_player.delete()
        finally:
            self.music_player = None

    # запуск уровня

    def reset(self) -> None:
        self.oxy = max(40, MAX_OXY - (self.lvl - 1) * 10)
        self.t_alive = 0.0
        self.anim_timer = 0.0

        self.walls = arcade.SpriteList()
        self.phys_walls = arcade.SpriteList()
        self.foes = arcade.SpriteList()
        self.oxy_pick = arcade.SpriteList()
        self.exits = arcade.SpriteList()
        self.emitters = []

        self.p = None
        self.phys = None
        self.dead_played = False
        self.stop_music()

        map_name = f"levels{self.lvl:02d}.tmx"
        print(f"Загружаю карту: {map_name}")

        try:
            m = arcade.load_tilemap(DATA / map_name)
        except Exception as e:
            print(f"Ошибка карты: {e}")
            self.state = STATE_CLEAR
            return

        start_x = 80
        start_y = 80

        for layer in m.sprite_lists.values():
            for it in layer:
                if it.texture is None:
                    continue
                nm = it.texture.name.lower()

                if "wall" in nm or "стен" in nm:
                    self.walls.append(it)
                    self.phys_walls.append(it)
                elif "door" in nm or "двер" in nm:
                    self.exits.append(it)
                elif "oxygen" in nm or "кисл" in nm or "oxigen" in nm:
                    amt = float(it.properties.get("fill", 25))
                    it.properties["fill"] = amt
                    self.oxy_pick.append(it)
                elif "enemy" in nm:
                    it.texture = self.enemy_tex[0]
                    self.foes.append(it)

        self.p = arcade.Sprite()
        self.p.texture = self.player_tex[0]
        self.p.center_x = start_x
        self.p.center_y = start_y

        self.phys = arcade.PhysicsEngineSimple(self.p, self.phys_walls)
        self.snap_camera_to_player()

        self.play_sound(self.s_start, 0.5)
        self.start_music()

        self.state = STATE_PLAY

    def advance_level(self) -> None:
        self.lvl += 1
        if self.lvl > self.lvl_max:
            self.state = STATE_CLEAR
            return
        self.reset()

    # рисуем на экране

    def on_draw(self) -> None:
        self.clear()

        self.cam.use()
        if self.state in (STATE_PLAY, STATE_OVER, STATE_CLEAR):
            self.walls.draw()
            self.oxy_pick.draw()
            self.foes.draw()
            self.exits.draw()
            if self.p:
                self.p.draw()
            for em in list(self.emitters):
                em.draw()

        self.cam_ui.use()
        if self.state == STATE_MENU:
            arcade.draw_text(TITLE, 80, self.height * 0.6, arcade.color.WHITE, 36)
            arcade.draw_text("WASD: ходьба", 120, self.height * 0.5, arcade.color.LIGHT_GRAY, 16)
            arcade.draw_text("SPACE: старт", 120, self.height * 0.45, arcade.color.LIGHT_GRAY, 16)
        elif self.state == STATE_PLAY:
            self.draw_hud()
        elif self.state == STATE_OVER:
            arcade.draw_text("Кислород закончился", 120, self.height * 0.55, arcade.color.APRICOT, 28)
            arcade.draw_text("SPACE: попытка снова", 120, self.height * 0.48, arcade.color.LIGHT_GRAY, 16)
            self.draw_stats()
        elif self.state == STATE_CLEAR:
            arcade.draw_text("Все уровни пройдены", 120, self.height * 0.55, arcade.color.ELECTRIC_GREEN, 28)
            arcade.draw_text("SPACE: сыграть ещё", 120, self.height * 0.48, arcade.color.LIGHT_GRAY, 16)
            self.draw_stats()

    def draw_hud(self) -> None:
        r = max(0.0, min(1.0, self.oxy / MAX_OXY))
        bw = 220
        bh = 20
        x0 = 20
        y0 = self.height - 40
        arcade.draw_rectangle_filled(x0 + bw / 2, y0, bw, bh, arcade.color.DAVY_GREY)
        arcade.draw_rectangle_filled(x0 + (bw * r) / 2, y0, bw * r, bh, arcade.color.AIR_FORCE_BLUE)
        arcade.draw_text(f"O2: {self.oxy:0.0f}%", x0, y0 + 16, arcade.color.WHITE_SMOKE, 14)
        arcade.draw_text(f"Уровень: {self.lvl}", x0, y0 - 32, arcade.color.LIGHT_GRAY, 14)
        arcade.draw_text(f"Время: {self.t_alive:0.1f}s", x0, y0 - 52, arcade.color.LIGHT_GRAY, 14)
        if self.oxy <= LOW_OXY_THRESHOLD:
            arcade.draw_text("Мало кислорода!", x0, y0 - 72, arcade.color.APRICOT, 14)

    def draw_stats(self) -> None:
        arcade.draw_text(f"Прошло времени: {self.t_alive:0.1f}s", 120, self.height * 0.38, arcade.color.LIGHT_GRAY, 16)
        arcade.draw_text(f"Последний уровень: {self.lvl}", 120, self.height * 0.32, arcade.color.LIGHT_GRAY, 16)

    # обновление игры

    def on_update(self, dt: float) -> None:
        if self.state != STATE_PLAY or not self.p or not self.phys:
            return

        self.t_alive += dt
        self.oxy -= OXY_DRAIN_PER_SEC * dt

        self.update_player_vel()
        self.phys.update()
        self.update_foes(dt)
        self.handle_collisions()
        self.update_emitters()
        self.update_camera()

        # тут будет анимация и эффекты, но в другом файле
        self.update_animation(dt)

        if self.oxy <= 0:
            if not self.dead_played:
                self.play_sound(self.s_dead, 0.6)
                self.stop_music()
                self.dead_played = True
            self.state = STATE_OVER

    def update_player_vel(self) -> None:
        if not self.p:
            return
        vx = 0
        vy = 0
        if self.mv_l:
            vx -= PLAYER_SPEED
        if self.mv_r:
            vx += PLAYER_SPEED
        if self.mv_u:
            vy += PLAYER_SPEED
        if self.mv_d:
            vy -= PLAYER_SPEED
        if vx and vy:
            s = 1 / math.sqrt(2)
            vx *= s
            vy *= s
        self.p.change_x = vx
        self.p.change_y = vy

    def update_foes(self, dt: float) -> None:
        if not self.p:
            return
        for foe in self.foes:
            x0 = foe.center_x
            y0 = foe.center_y

            dx = self.p.center_x - foe.center_x
            dy = self.p.center_y - foe.center_y
            dist = math.hypot(dx, dy)
            if dist:
                step = ENEMY_SPEED * dt
                foe.center_x += (dx / dist) * step
                if arcade.check_for_collision_with_list(foe, self.phys_walls):
                    foe.center_x = x0
                foe.center_y += (dy / dist) * step
                if arcade.check_for_collision_with_list(foe, self.phys_walls):
                    foe.center_y = y0

    def handle_collisions(self) -> None:
        if not self.p:
            return

        hit = arcade.check_for_collision_with_list(self.p, self.foes)
        if hit:
            self.oxy -= OXY_HIT_LOSS
            self.spawn_fx(self.p.position, arcade.color.BARN_RED)

        for b in arcade.check_for_collision_with_list(self.p, self.oxy_pick):
            fill = b.properties.get("fill", 25)
            self.oxy = min(MAX_OXY, self.oxy + fill)
            b.remove_from_sprite_lists()
            self.spawn_fx(b.position, arcade.color.SPRING_GREEN)
            self.play_sound(self.s_pick, 0.35)

        if arcade.check_for_collision_with_list(self.p, self.exits):
            self.advance_level()

    # тут специально пусто, это будет в другом файле

    def update_animation(self, dt: float) -> None:
        # анимации нет, это сделает main.py
        pass

    def spawn_fx(self, pos: tuple[float, float], col: arcade.Color) -> None:
        # эффектов нет, это сделает main.py
        pass

    # частицы и камера

    def update_emitters(self) -> None:
        for em in list(self.emitters):
            em.update()
            if em.can_reap():
                self.emitters.remove(em)

    def update_camera(self) -> None:
        if not self.p:
            return
        target = (self.p.center_x - self.width / 2, self.p.center_y - self.height / 2)
        self.cam.move_to(target, 0.25)

    def snap_camera_to_player(self) -> None:
        if not self.p:
            return
        target = (self.p.center_x - self.width / 2, self.p.center_y - self.height / 2)
        self.cam.move_to(target, 1.0)

    # нажатия клавиш

    def on_key_press(self, sym: int, mod: int) -> None:
        if self.state == STATE_MENU and sym == arcade.key.SPACE:
            self.lvl = 1
            self.lvl_max = 5
            self.reset()
            return

        if self.state in (STATE_OVER, STATE_CLEAR) and sym == arcade.key.SPACE:
            self.lvl = 1
            self.reset()
            return

        if self.state != STATE_PLAY:
            return

        if sym in (arcade.key.A, arcade.key.LEFT):
            self.mv_l = True
        if sym in (arcade.key.D, arcade.key.RIGHT):
            self.mv_r = True
        if sym in (arcade.key.W, arcade.key.UP):
            self.mv_u = True
        if sym in (arcade.key.S, arcade.key.DOWN):
            self.mv_d = True

    def on_key_release(self, sym: int, mod: int) -> None:
        if self.state != STATE_PLAY:
            return

        if sym in (arcade.key.A, arcade.key.LEFT):
            self.mv_l = False
        if sym in (arcade.key.D, arcade.key.RIGHT):
            self.mv_r = False
        if sym in (arcade.key.W, arcade.key.UP):
            self.mv_u = False
        if sym in (arcade.key.S, arcade.key.DOWN):
            self.mv_d = False