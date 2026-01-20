import arcade
try:
    print(f"arcade.Camera exists: {hasattr(arcade, 'Camera')}")
except:
    print("Error checking arcade.Camera")

try:
    print(f"arcade.Camera2D exists: {hasattr(arcade, 'Camera2D')}")
    if hasattr(arcade, 'Camera2D'):
        print(dir(arcade.Camera2D))
except:
    print("Error checking arcade.Camera2D")

try:
    print(f"arcade.PymunkPhysicsEngine exists: {hasattr(arcade, 'PymunkPhysicsEngine')}")
except:
    print("Error checking arcade.PymunkPhysicsEngine")
