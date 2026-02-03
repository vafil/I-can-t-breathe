from __future__ import annotations

import csv
import math
import pathlib
import random
from dataclasses import dataclass
import arcade

SCREEN_W = 960
SCREEN_H = 640
TITLE = "I Can't Breathe"

# Пути к папкам
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"

# Константы
PLAYER_SPEED = 5
ENEMY_SPEED = 140
PLAYER_W = 32
PLAYER_H = 32
OXY_DRAIN_PER_SEC = 6
OXY_HIT_LOSS = 18
LOW_OXY_THRESHOLD = 25
MAX_OXY = 100

# Состояния
STATE_MENU = "menu"
STATE_PLAY = "play"
STATE_OVER = "over"
STATE_CLEAR = "clear"

# Цвет
WALL_COLOR = arcade.color.DARK_SLATE_GRAY

# Данные об одном объекте
@dataclass
class LevelRow:
    kind: str
    x: float
    y: float
    w: float
    h: float
    param: float

# Загрузка объектов
def load_level_rows(level_id: int) -> list[LevelRow]:
    rows: list[LevelRow] = []
    csv_path = DATA / "levels.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing level data: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            try:
                if int(raw.get("level", 0)) != level_id:
                    continue
                rows.append(
                    LevelRow(
                        kind=raw.get("kind", "").strip().lower(),
                        x=float(raw.get("x", 0)),
                        y=float(raw.get("y", 0)),
                        w=float(raw.get("w", 0)),
                        h=float(raw.get("h", 0)),
                        param=float(raw.get("param", 0)),
                    )
                )
            except ValueError:
                continue
    return rows


# Максимальный номер уровня из csv(это если добавлять больше уровней будет)
def max_level_id() -> int:
    csv_path = DATA / "levels.csv"
    if not csv_path.exists():
        return 1
    highest = 1
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            try:
                highest = max(highest, int(raw.get("level", 1)))
            except ValueError:
                continue
    return highest


# Мэин виндоу
class GameWindow(arcade.Window):
    def __init__(self) -> None:
        super().__init__(SCREEN_W, SCREEN_H, TITLE, update_rate=1 / 60)
        arcade.set_background_color(arcade.color.BLACK_OLIVE)

        # Коунтерс
        self.state: str = STATE_MENU        # текущее состояние (меню, игра и т.д.)
        self.lvl: int = 1                   # текущий уровень
        self.lvl_max: int = max_level_id()  # максимальный уровень
        self.oxy: float = MAX_OXY           # кислород игрока
        self.t_alive: float = 0.0           # сколько живет игрок

        # Физикс и спрайтс
        self.p: arcade.Sprite | None = None # игрок
        self.phys: arcade.PhysicsEngineSimple | None = None # физика игрока
        self.walls: arcade.SpriteList = arcade.SpriteList() # стены
        self.phys_walls: arcade.SpriteList = arcade.SpriteList() # стены для физики
        self.foes: arcade.SpriteList = arcade.SpriteList()  # враги
        self.oxy_pick: arcade.SpriteList = arcade.SpriteList() # баллоны кислорода
        self.exits: arcade.SpriteList = arcade.SpriteList() # выходы
        self.emitters: list[arcade.Emitter] = []           # частицы
        self.foe_dir: dict[arcade.Sprite, tuple[float, float]] = {} # направления врагов (не используется)

        # Текстуры
        try:
            self.tex_player = arcade.load_texture(ASSETS / "models" / "player.jpg")
        except Exception:
            self.tex_player = None
            
        try:
            self.tex_enemy = arcade.load_texture(ASSETS / "models" / "enemy.jpg")
        except Exception:
            self.tex_enemy = None
            
        try:
            self.tex_wall = arcade.load_texture(ASSETS / "textures" / "wall.jpg")
        except Exception:
            self.tex_wall = None

        try:
            self.tex_exit = arcade.load_texture(ASSETS / "textures" / "door.jpg")
        except Exception:
            self.tex_exit = None
        
        try:
            self.tex_oxy = arcade.load_texture(ASSETS / "textures" / "oxygen.jpg")
        except Exception as e:
            self.tex_oxy = None

        # Аудио
        def load_wav(name):
             path = ASSETS / "audio" / f"{name}.wav"
             return arcade.load_sound(path) if path.exists() else None

        self.s_pick = load_wav("pickup")
        self.s_dead = load_wav("death")
        self.s_music = load_wav("music")
        self.s_start = load_wav("start")
        
        self.music_player: object | None = None # проигрыватель
        self.dead_played = False # звук смерти

        # WASD
        self.mv_l = False
        self.mv_r = False
        self.mv_u = False
        self.mv_d = False

        # Камеры
        self.cam = arcade.Camera(self.width, self.height)
        self.cam_ui = arcade.Camera(self.width, self.height)

    def reset(self) -> None:
        # Сброс
        self.oxy = max(40, MAX_OXY - (self.lvl - 1) * 10)
        self.t_alive = 0.0

        # Убрать списки спрайтов и тд
        self.walls = arcade.SpriteList()
        self.phys_walls = arcade.SpriteList()
        self.foes = arcade.SpriteList()
        self.oxy_pick = arcade.SpriteList()
        self.exits = arcade.SpriteList()
        self.phys = None
        self.p = None
        self.emitters = []
        self.foe_dir = {}
        self.dead_played = False
        self.stop_music()

        # Загрузка
        rows = load_level_rows(self.lvl)
        if not rows:
            self.state = STATE_CLEAR
            return

        # Старт игрока
        start_x = 80
        start_y = 80
        for row in rows:
            if row.kind == "start":
                start_x, start_y = row.x, row.y

        # Создание игрока
        if self.tex_player:
            self.p = arcade.Sprite()
            self.p.texture = self.tex_player
            self.p.width = PLAYER_W
            self.p.height = PLAYER_H
        else:
            self.p = arcade.SpriteSolidColor(PLAYER_W, PLAYER_H, arcade.color.LIGHT_BLUE)
        self.p.center_x = start_x
        self.p.center_y = start_y

        # Карта
        for row in rows:
            if row.kind == "wall":
                # Физ стены
                p_wall = arcade.SpriteSolidColor(int(row.w), int(row.h), arcade.color.WHITE)
                p_wall.center_x, p_wall.center_y = row.x, row.y
                p_wall.alpha = 0
                self.phys_walls.append(p_wall)

                # Виз стена
                if self.tex_wall:
                    tiles = self.make_tiled_sprites(self.tex_wall, int(row.w), int(row.h), row.x, row.y)
                    self.walls.extend(tiles)
                else:
                    wall = arcade.SpriteSolidColor(int(row.w), int(row.h), WALL_COLOR)
                    wall.center_x, wall.center_y = row.x, row.y
                    self.walls.append(wall)
            elif row.kind == "enemy":
                # Врага
                if self.tex_enemy:
                    foe = arcade.Sprite()
                    foe.texture = self.tex_enemy
                    foe.width = 28
                    foe.height = 28
                else:
                    foe = arcade.SpriteSolidColor(28, 28, arcade.color.BARN_RED)
                foe.center_x = row.x
                foe.center_y = row.y
                self.foes.append(foe)
                self.foe_dir[foe] = (random.choice([-1.0, 1.0]), random.choice([-1.0, 1.0]))
            elif row.kind == "oxy":
                # Балоны
                if self.tex_oxy:
                    bottle = arcade.Sprite()
                    bottle.texture = self.tex_oxy
                    bottle.width = 16
                    bottle.height = 24
                else:
                    bottle = arcade.SpriteSolidColor(16, 24, arcade.color.SPRING_GREEN)
                bottle.center_x, bottle.center_y = row.x, row.y
                bottle.properties["fill"] = row.param if row.param else 25
                self.oxy_pick.append(bottle)
            elif row.kind == "exit":
                # Выход
                if self.tex_exit:
                    goal = arcade.Sprite()
                    goal.texture = self.tex_exit
                    goal.width = 64
                    goal.height = 64
                else:
                    goal = arcade.SpriteSolidColor(30, 30, arcade.color.YELLOW_ORANGE)
                goal.center_x, goal.center_y = row.x, row.y
                self.exits.append(goal)

        # Физикс
        if self.p:
            self.phys = arcade.PhysicsEngineSimple(self.p, self.phys_walls)
            self.snap_camera_to_player()
            self.play_sound(self.s_start, 0.5)
            self.start_music()

        self.state = STATE_PLAY

    def on_draw(self) -> None:
        self.clear()

        self.cam.use()
        # Рисуем объекты уровня, если играем или проиграли/прошли
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
        # Рисуем меню
        if self.state == STATE_MENU:
            arcade.draw_text(TITLE, 80, self.height * 0.6, arcade.color.WHITE, 36)
            arcade.draw_text("WASD: ходьба", 120, self.height * 0.5, arcade.color.LIGHT_GRAY, 16)
            arcade.draw_text("SPACE: старт", 120, self.height * 0.45, arcade.color.LIGHT_GRAY, 16)
        # HUD
        elif self.state == STATE_PLAY:
            self.draw_hud()
        # Экран проигрыша
        elif self.state == STATE_OVER:
            arcade.draw_text("Кислород закончился", 120, self.height * 0.55, arcade.color.APRICOT, 28)
            arcade.draw_text("SPACE: попытка снова", 120, self.height * 0.48, arcade.color.LIGHT_GRAY, 16)
            self.draw_stats()
        # Экран победы
        elif self.state == STATE_CLEAR:
            arcade.draw_text("Все уровни пройдены", 120, self.height * 0.55, arcade.color.ELECTRIC_GREEN, 28)
            arcade.draw_text("SPACE: сыграть ещё", 120, self.height * 0.48, arcade.color.LIGHT_GRAY, 16)
            self.draw_stats()

    def draw_hud(self) -> None:
        # Кислород и инфа
        oxy_ratio = max(0.0, min(1.0, self.oxy / MAX_OXY))
        bar_w = 220
        bar_h = 20
        x0 = 20
        y0 = self.height - 40
        arcade.draw_rectangle_filled(x0 + bar_w / 2, y0, bar_w, bar_h, arcade.color.DAVY_GREY)
        arcade.draw_rectangle_filled(x0 + (bar_w * oxy_ratio) / 2, y0, bar_w * oxy_ratio, bar_h, arcade.color.AIR_FORCE_BLUE)
        arcade.draw_text(f"O2: {self.oxy:0.0f}%", x0, y0 + 16, arcade.color.WHITE_SMOKE, 14)
        arcade.draw_text(f"Уровень: {self.lvl}", x0, y0 - 32, arcade.color.LIGHT_GRAY, 14)
        arcade.draw_text(f"Время: {self.t_alive:0.1f}s", x0, y0 - 52, arcade.color.LIGHT_GRAY, 14)
        if self.oxy <= LOW_OXY_THRESHOLD:
            arcade.draw_text("Мало кислорода!", x0, y0 - 72, arcade.color.APRICOT, 14)

    def draw_stats(self) -> None:
        # Статистика
        arcade.draw_text(f"Прошло времени: {self.t_alive:0.1f}s", 120, self.height * 0.38, arcade.color.LIGHT_GRAY, 16)
        arcade.draw_text(f"Последний уровень: {self.lvl}", 120, self.height * 0.32, arcade.color.LIGHT_GRAY, 16)

    def on_update(self, delta_time: float) -> None:
        # заново играем(игровой цикл)
        if self.state != STATE_PLAY or not self.p or not self.phys:
            return

        self.t_alive += delta_time
        self.oxy -= OXY_DRAIN_PER_SEC * delta_time

        self.update_player_velocity()
        self.phys.update()
        self.clamp_player_to_screen()
        self.update_foes(delta_time)
        self.handle_collisions()
        self.update_emitters()
        self.update_camera()

        # Условия для пройгрыша
        if self.oxy <= 0:
            if not self.dead_played:
                self.play_sound(self.s_dead, 0.6)
                self.stop_music()
                self.dead_played = True
            self.state = STATE_OVER

    def update_player_velocity(self) -> None:
        # Управление
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
            scale = 1 / math.sqrt(2)
            vx *= scale
            vy *= scale
        self.p.change_x = vx
        self.p.change_y = vy

    def update_foes(self, delta_time: float) -> None:
        # Враги тянутсяс к игроку
        if not self.p:
            return
        for foe in self.foes:
            x0 = foe.center_x
            y0 = foe.center_y

            dx = self.p.center_x - foe.center_x
            dy = self.p.center_y - foe.center_y
            dist = math.hypot(dx, dy)
            if dist:
                step = ENEMY_SPEED * delta_time
                move_x = (dx / dist) * step
                move_y = (dy / dist) * step
                foe.center_x += move_x
                if arcade.check_for_collision_with_list(foe, self.phys_walls):
                    foe.center_x = x0
                foe.center_y += move_y
                if arcade.check_for_collision_with_list(foe, self.phys_walls):
                    foe.center_y = y0
                if self.foe_hits_other(foe):
                    foe.center_x = x0
                    foe.center_y = y0

    def clamp_player_to_screen(self) -> None:
        # ограничение игрока экраном
        if not self.p:
            return
        self.p.center_x = max(0, min(self.width, self.p.center_x))
        self.p.center_y = max(0, min(self.height, self.p.center_y))

    def handle_collisions(self) -> None:
        if not self.p:
            return

        # урон
        hit_foes = arcade.check_for_collision_with_list(self.p, self.foes)
        if hit_foes:
            self.oxy -= OXY_HIT_LOSS
            self.spawn_fx(self.p.position, arcade.color.BARN_RED)

        # кислород из балонов
        for bottle in arcade.check_for_collision_with_list(self.p, self.oxy_pick):
            fill = bottle.properties.get("fill", 25)
            self.oxy = min(MAX_OXY, self.oxy + fill)
            bottle.remove_from_sprite_lists()
            self.spawn_fx(bottle.position, arcade.color.SPRING_GREEN)
            self.play_sound(self.s_pick, 0.35)

        # След уровень
        if arcade.check_for_collision_with_list(self.p, self.exits):
            self.advance_level()

    def foe_hits_other(self, spr: arcade.Sprite) -> bool:
        # Колижон врагов
        for other in self.foes:
            if other is spr:
                continue
            if spr.collides_with_sprite(other):
                return True
        return False


# Частицы и враги обновление
    def update_emitters(self) -> None:
        for em in list(self.emitters):
            em.update()
            if em.can_reap():
                self.emitters.remove(em)
# Эффекты частиц
    def spawn_fx(self, pos: tuple[float, float], color: arcade.Color) -> None:
        texture = arcade.make_soft_circle_texture(6, color, 96, 255)
        em = arcade.Emitter(
            center_xy=pos,
            emit_controller=arcade.EmitterIntervalWithTime(0.02, 0.15),
            particle_factory=lambda emitter: arcade.LifetimeParticle(
                filename_or_texture=texture,
                change_xy=(random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5)),
                lifetime=random.uniform(0.2, 0.5),
                scale=1.0,
                alpha=220,
            ),
        )
        self.emitters.append(em)
# Камера
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



    def play_sound(self, snd: arcade.Sound | None, vol: float = 0.6, loop: bool = False) -> None:
        # sound
        if snd:
            try:
                return snd.play(volume=vol, loop=loop)
            except Exception:
                return None
        return None

    def make_tiled_sprites(
        self, tex: arcade.Texture, w: int, h: int, center_x: float, center_y: float
    ) -> list[arcade.Sprite]:
        # tiels for texture
        tiles: list[arcade.Sprite] = []
        tile_step = max(8, int(min(tex.width, tex.height) / 2))
        tw = tile_step
        th = tile_step
        x0 = center_x - w / 2
        y0 = center_y - h / 2
        nx = max(1, math.ceil(w / tw))
        ny = max(1, math.ceil(h / th))
        for ix in range(nx):
            for iy in range(ny):
                span_w = min(tw, w - ix * tw)
                span_h = min(th, h - iy * th)
                tile = arcade.Sprite()
                tile.texture = tex
                tile.width = span_w
                tile.height = span_h
                tile.center_x = x0 + ix * tw + span_w / 2
                tile.center_y = y0 + iy * th + span_h / 2
                tiles.append(tile)
        return tiles

    def start_music(self) -> None:
        # music if no sound
        if self.s_music and not self.music_player:
            self.music_player = self.play_sound(self.s_music, vol=0.25, loop=True)

    def stop_music(self) -> None:
        # no more music
        try:
            if self.music_player and hasattr(self.music_player, "pause"):
                self.music_player.pause()
            if self.music_player and hasattr(self.music_player, "delete"):
                self.music_player.delete()
        finally:
            self.music_player = None

    def advance_level(self) -> None:
        # next level
        self.lvl += 1
        if self.lvl > self.lvl_max:
            self.state = STATE_CLEAR
            return
        self.reset()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        # Нажатия
        if self.state == STATE_MENU and symbol == arcade.key.SPACE:
            self.lvl = 1
            self.lvl_max = max_level_id()
            self.reset()
            return
        if self.state in (STATE_OVER, STATE_CLEAR) and symbol == arcade.key.SPACE:
            self.lvl = 1
            self.reset()
            return
        if self.state != STATE_PLAY:
            return

        # WASD/стрелки
        if symbol in (arcade.key.A, arcade.key.LEFT):
            self.mv_l = True
        if symbol in (arcade.key.D, arcade.key.RIGHT):
            self.mv_r = True
        if symbol in (arcade.key.W, arcade.key.UP):
            self.mv_u = True
        if symbol in (arcade.key.S, arcade.key.DOWN):
            self.mv_d = True

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        # Спуск клавиш
        if self.state != STATE_PLAY:
            return

        if symbol in (arcade.key.A, arcade.key.LEFT):
            self.mv_l = False
        if symbol in (arcade.key.D, arcade.key.RIGHT):
            self.mv_r = False
        if symbol in (arcade.key.W, arcade.key.UP):
            self.mv_u = False
        if symbol in (arcade.key.S, arcade.key.DOWN):
            self.mv_d = False


# Точка входа
def main() -> None:
    window = GameWindow()
    arcade.run()


if __name__ == "__main__":
    main()
