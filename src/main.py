from __future__ import annotations

import csv
import math
import pathlib
import random
from dataclasses import dataclass

import arcade
import pymunk
from pyglet.window import key as pyglet_key

SCREEN_W = 960
SCREEN_H = 640
TITLE = "I Can't Breathe"

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"

PLAYER_SPEED = 180
ENEMY_WANDER_SPEED = 110
ENEMY_CHASE_SPEED = 150
OXY_DRAIN_PER_SEC = 6
OXY_HIT_LOSS = 18
LOW_OXY_THRESHOLD = 25
MAX_OXY = 100

STATE_MENU = "menu"
STATE_PLAY = "play"
STATE_OVER = "over"
STATE_CLEAR = "clear"

WALL_COLOR = arcade.color.DARK_SLATE_GRAY
DOOR_COLOR = WALL_COLOR


@dataclass
class LevelRow:
    kind: str
    x: float
    y: float
    w: float
    h: float
    param: float


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


class AudioSet:
    def __init__(self) -> None:
        self.breath = self._safe_load(ASSETS / "audio" / "breath.wav")
        self.alarm = self._safe_load(ASSETS / "audio" / "alarm.wav")
        self.pick = self._safe_load(ASSETS / "audio" / "pickup.wav")
        self.hit = self._safe_load(ASSETS / "audio" / "hit.wav")

    def _safe_load(self, path: pathlib.Path) -> arcade.Sound | None:
        if path.exists():
            try:
                return arcade.load_sound(path)
            except Exception:
                return None
        return None

    def play(self, sound: arcade.Sound | None, loop: bool = False, volume: float = 0.7) -> None:
        if sound:
            try:
                sound.play(volume=volume, loop=loop)
            except Exception:
                pass


class GameWindow(arcade.Window):
    def __init__(self) -> None:
        super().__init__(SCREEN_W, SCREEN_H, TITLE, update_rate=1 / 60)
        arcade.set_background_color(arcade.color.BLACK_OLIVE)

        self.state: str = STATE_MENU
        self.level_id: int = 1
        self.max_level: int = max_level_id()
        self.oxy: float = MAX_OXY
        self.time_alive: float = 0.0

        self.player: arcade.Sprite | None = None
        self.physics: arcade.PymunkPhysicsEngine | None = None
        self.walls: arcade.SpriteList = arcade.SpriteList()
        self.enemies: arcade.SpriteList = arcade.SpriteList()
        self.oxies: arcade.SpriteList = arcade.SpriteList()
        self.doors: arcade.SpriteList = arcade.SpriteList()
        self.exits: arcade.SpriteList = arcade.SpriteList()
        self.emitters: list[arcade.Emitter] = []

        self.enemy_plan: dict[arcade.Sprite, tuple[float, float, float]] = {}
        self.enemy_meta: dict[arcade.Sprite, dict[str, float | tuple[float, float] | str]] = {}
        self.move_x = 0
        self.move_y = 0
        self.keys = pyglet_key.KeyStateHandler()
        self.push_handlers(self.keys)

        self.camera = arcade.Camera(self.width, self.height)
        self.ui_camera = arcade.Camera(self.width, self.height)

        self.sounds = AudioSet()
        self.low_alarm_on = False

    def reset(self) -> None:
        self.oxy = MAX_OXY - (self.level_id - 1) * 10
        self.oxy = max(40, self.oxy)
        self.time_alive = 0.0
        self.move_x = 0
        self.move_y = 0
        self.low_alarm_on = False

        self.walls = arcade.SpriteList()
        self.enemies = arcade.SpriteList()
        self.oxies = arcade.SpriteList()
        self.doors = arcade.SpriteList()
        self.exits = arcade.SpriteList()
        self.emitters = []
        self.enemy_plan = {}
        self.enemy_meta = {}

        self.physics = arcade.PymunkPhysicsEngine(damping=0.92, gravity=(0, 0))

        rows = load_level_rows(self.level_id)
        if not rows:
            self.state = STATE_CLEAR
            return

        start_x = SCREEN_W * 0.1
        start_y = SCREEN_H * 0.1

        for row in rows:
            if row.kind == "start":
                start_x, start_y = row.x, row.y

        self.player = arcade.SpriteSolidColor(32, 32, arcade.color.LIGHT_BLUE)
        # Чуть меньше хитбокс, чем визуальная плитка, чтобы не застревать в узких проёмах
        self.player.set_hit_box([(-12, -12), (12, -12), (12, 12), (-12, 12)])
        self.player.center_x = start_x
        self.player.center_y = start_y
        self.physics.add_sprite(
            self.player,
            mass=2,
            friction=0.4,
            moment=arcade.PymunkPhysicsEngine.MOMENT_INF,
            max_velocity=260,
            collision_type="player",
        )

        for row in rows:
            if row.kind == "wall":
                wall = arcade.SpriteSolidColor(int(row.w), int(row.h), WALL_COLOR)
                wall.center_x = row.x
                wall.center_y = row.y
                self.walls.append(wall)
                self.physics.add_sprite(wall, body_type=pymunk.Body.STATIC, collision_type="wall")
            elif row.kind == "enemy":
                foe = arcade.SpriteSolidColor(28, 28, arcade.color.BARN_RED)
                foe.set_hit_box([(-10, -10), (10, -10), (10, 10), (-10, 10)])
                foe.center_x, foe.center_y = row.x, row.y
                self.enemies.append(foe)
                self.physics.add_sprite(
                    foe,
                    mass=1.5,
                    friction=0.2,
                    moment=arcade.PymunkPhysicsEngine.MOMENT_INF,
                    collision_type="enemy",
                )
                wiggle = max(40, row.param if row.param else 70)
                self.enemy_plan[foe] = (foe.center_x, foe.center_y, wiggle)
                self.enemy_meta[foe] = {"mode": "wander", "dir": (random.uniform(-1, 1), random.uniform(-1, 1)), "timer": 0.0}
            elif row.kind == "oxy":
                bottle = arcade.SpriteSolidColor(16, 24, arcade.color.SPRING_GREEN)
                bottle.center_x, bottle.center_y = row.x, row.y
                bottle.properties["fill"] = row.param if row.param else 25
                self.oxies.append(bottle)
            elif row.kind == "door":
                door = arcade.SpriteSolidColor(int(row.w), int(row.h), DOOR_COLOR)
                door.center_x, door.center_y = row.x, row.y
                self.doors.append(door)
                self.physics.add_sprite(door, body_type=pymunk.Body.STATIC, collision_type="door")
            elif row.kind == "exit":
                goal = arcade.SpriteSolidColor(30, 30, arcade.color.YELLOW_ORANGE)
                goal.center_x, goal.center_y = row.x, row.y
                self.exits.append(goal)

        if self.doors:
            self.walls.extend(self.doors)

        self.state = STATE_PLAY

    def on_draw(self) -> None:
        self.clear()
        self.camera.use()

        if self.state in (STATE_PLAY, STATE_CLEAR, STATE_OVER):
            self.walls.draw()
            self.oxies.draw()
            self.enemies.draw()
            self.exits.draw()
            if self.player:
                self.player.draw()
            for emitter in list(self.emitters):
                emitter.draw()

        self.ui_camera.use()
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
        oxy_ratio = max(0.0, min(1.0, self.oxy / MAX_OXY))
        bar_w = 220
        bar_h = 20
        x0 = 20
        y0 = self.height - 40
        arcade.draw_rectangle_filled(x0 + bar_w / 2, y0, bar_w, bar_h, arcade.color.DAVY_GREY)
        arcade.draw_rectangle_filled(x0 + (bar_w * oxy_ratio) / 2, y0, bar_w * oxy_ratio, bar_h, arcade.color.AIR_FORCE_BLUE)
        arcade.draw_text(f"O2: {self.oxy:0.0f}%", x0, y0 + 16, arcade.color.WHITE_SMOKE, 14)
        arcade.draw_text(f"Уровень: {self.level_id}", x0, y0 - 32, arcade.color.LIGHT_GRAY, 14)
        arcade.draw_text(f"Время: {self.time_alive:0.1f}s", x0, y0 - 52, arcade.color.LIGHT_GRAY, 14)

    def draw_stats(self) -> None:
        arcade.draw_text(f"Прошло времени: {self.time_alive:0.1f}s", 120, self.height * 0.38, arcade.color.LIGHT_GRAY, 16)
        arcade.draw_text(f"Последний уровень: {self.level_id}", 120, self.height * 0.32, arcade.color.LIGHT_GRAY, 16)

    def on_update(self, delta_time: float) -> None:
        if self.state != STATE_PLAY or not self.player or not self.physics:
            return

        self.time_alive += delta_time
        self.oxy -= OXY_DRAIN_PER_SEC * delta_time

        self.update_move_from_keys()

        mag = math.hypot(self.move_x, self.move_y)
        if mag > 0:
            scale = PLAYER_SPEED / mag
            speed_x = self.move_x * scale
            speed_y = self.move_y * scale
        else:
            speed_x = 0
            speed_y = 0
        self.physics.set_velocity(self.player, (speed_x, speed_y))

        prev_player = (self.player.center_x, self.player.center_y)
        prev_enemies = {e: (e.center_x, e.center_y) for e in self.enemies}

        self.move_enemies(delta_time)
        self.physics.step(delta_time)

        self.resolve_blocking(prev_player, prev_enemies)
        self.handle_collisions()
        self.update_emitters(delta_time)
        self.update_alarm()
        self.update_camera()

        if self.oxy <= 0:
            self.state = STATE_OVER

    def update_move_from_keys(self) -> None:
        key = pyglet_key
        mx = 0
        my = 0
        if self.keys[key.W] or self.keys[key.UP]:
            my += 1
        if self.keys[key.S] or self.keys[key.DOWN]:
            my -= 1
        if self.keys[key.A] or self.keys[key.LEFT]:
            mx -= 1
        if self.keys[key.D] or self.keys[key.RIGHT]:
            mx += 1
        self.move_x = mx
        self.move_y = my

    def move_enemies(self, delta_time: float) -> None:
        if not self.physics or not self.player:
            return

        for enemy, plan in list(self.enemy_plan.items()):
            home_x, home_y, sway = plan
            meta = self.enemy_meta.get(enemy, {"mode": "wander", "dir": (1.0, 0.0), "timer": 0.0})

            can_see = self.has_line_of_sight(enemy)

            if can_see:
                meta["mode"] = "chase"
                dx = self.player.center_x - enemy.center_x
                dy = self.player.center_y - enemy.center_y
                dist = math.hypot(dx, dy)
                if dist:
                    vx = (dx / dist) * ENEMY_CHASE_SPEED
                    vy = (dy / dist) * ENEMY_CHASE_SPEED
                    self.physics.set_velocity(enemy, (vx, vy))
            else:
                meta["mode"] = "wander"
                timer = float(meta.get("timer", 0.0)) - delta_time
                dir_x, dir_y = meta.get("dir", (0.0, 0.0))  # type: ignore
                if timer <= 0 or (dir_x == 0 and dir_y == 0):
                    angle = random.uniform(0, math.tau)
                    dir_x = math.cos(angle)
                    dir_y = math.sin(angle)
                    timer = random.uniform(0.8, 1.8)
                vx = dir_x * ENEMY_WANDER_SPEED
                vy = dir_y * ENEMY_WANDER_SPEED
                self.physics.set_velocity(enemy, (vx, vy))
                meta["dir"] = (dir_x, dir_y)
                meta["timer"] = timer

            self.enemy_meta[enemy] = meta

    def has_line_of_sight(self, enemy: arcade.Sprite) -> bool:
        if not self.player:
            return False
        # ограничим дальность обзора, чтобы игрок мог скрыться
        max_dist = 480
        dx = self.player.center_x - enemy.center_x
        dy = self.player.center_y - enemy.center_y
        if math.hypot(dx, dy) > max_dist:
            return False
        # проверяем прямую видимость с учётом стен и дверей
        blockers = self.walls
        return arcade.has_line_of_sight(enemy.position, self.player.position, blockers)

    def resolve_blocking(self, prev_player: tuple[float, float], prev_enemies: dict[arcade.Sprite, tuple[float, float]]) -> None:
        def separate(sprite: arcade.Sprite, prev: tuple[float, float]) -> None:
            if not arcade.check_for_collision_with_list(sprite, self.walls):
                return
            sx0, sy0 = prev
            dx = sprite.center_x - sx0
            dy = sprite.center_y - sy0
            # сначала X
            sprite.center_x = sx0 + dx
            if arcade.check_for_collision_with_list(sprite, self.walls):
                sprite.center_x = sx0
                dx = 0
            # потом Y
            sprite.center_y = sy0 + dy
            if arcade.check_for_collision_with_list(sprite, self.walls):
                sprite.center_y = sy0
                dy = 0
            # если всё ещё застрял, откатить полностью
            if arcade.check_for_collision_with_list(sprite, self.walls):
                sprite.center_x, sprite.center_y = sx0, sy0
            if self.physics:
                self.physics.set_velocity(sprite, (0, 0))

        if self.player:
            separate(self.player, prev_player)

        for enemy, prev in prev_enemies.items():
            separate(enemy, prev)

    def handle_collisions(self) -> None:
        if not self.player:
            return

        hit_enemies = arcade.check_for_collision_with_list(self.player, self.enemies)
        if hit_enemies:
            self.oxy -= OXY_HIT_LOSS * min(1, len(hit_enemies))
            self.spawn_emitter(self.player.position, arcade.color.BARN_RED)
            self.sounds.play(self.sounds.hit, volume=0.3)

        hit_oxy = arcade.check_for_collision_with_list(self.player, self.oxies)
        for bottle in hit_oxy:
            fill = bottle.properties.get("fill", 25)
            self.oxy = min(MAX_OXY, self.oxy + fill)
            bottle.remove_from_sprite_lists()
            self.spawn_emitter(bottle.position, arcade.color.SPRING_GREEN)
            self.sounds.play(self.sounds.pick, volume=0.4)

        hit_exits = arcade.check_for_collision_with_list(self.player, self.exits)
        if hit_exits:
            self.advance_level()

    def update_emitters(self, delta_time: float) -> None:
        for emitter in list(self.emitters):
            emitter.update()
            if emitter.can_reap():
                self.emitters.remove(emitter)

    def update_alarm(self) -> None:
        low_now = self.oxy <= LOW_OXY_THRESHOLD
        if low_now and not self.low_alarm_on:
            self.low_alarm_on = True
            self.sounds.play(self.sounds.alarm, loop=False, volume=0.35)
        elif not low_now:
            self.low_alarm_on = False

    def update_camera(self) -> None:
        if not self.player:
            return
        target = self.player.position[0] - self.width / 2, self.player.position[1] - self.height / 2
        # более заметное запаздывание камеры
        self.camera.move_to(target, 0.035)

    def spawn_emitter(self, pos: tuple[float, float], color: arcade.Color) -> None:
        texture = arcade.make_soft_circle_texture(6, color, 64, 255)
        emitter = arcade.Emitter(
            center_xy=pos,
            emit_controller=arcade.EmitterIntervalWithTime(0.02, 0.2),
            particle_factory=lambda emitter: arcade.LifetimeParticle(
                filename_or_texture=texture,
                change_xy=(random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2)),
                lifetime=random.uniform(0.2, 0.6),
                scale=1.0,
                alpha=200,
            ),
        )
        self.emitters.append(emitter)

    def advance_level(self) -> None:
        self.level_id += 1
        if self.level_id > self.max_level:
            self.state = STATE_CLEAR
            return
        self.reset()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if self.state == STATE_MENU and symbol == arcade.key.SPACE:
            self.level_id = 1
            self.max_level = max_level_id()
            self.reset()
            return
        if self.state in (STATE_OVER, STATE_CLEAR) and symbol == arcade.key.SPACE:
            self.level_id = 1
            self.reset()
            return
        if self.state != STATE_PLAY:
            return
        # движение читается из KeyStateHandler в on_update; здесь ничего не меняем

    def on_text(self, text: str) -> None:
        if self.state != STATE_PLAY or not text:
            return
        # ввод текста для управления не используем — движение читается из KeyStateHandler
        return

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        if self.state != STATE_PLAY:
            return
        # движение обновляется в on_update через KeyStateHandler, здесь ничего не сбрасываем


def main() -> None:
    window = GameWindow()
    arcade.run()


if __name__ == "__main__":
    main()
