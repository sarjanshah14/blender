# Domino Chain Reaction — Complete Project Guide (for evaluation)

**Read this end to end once. It explains, in plain language, what the video
is, every object in the Blender file, the concepts behind them, how each
part is made *by hand in the Blender app*, and a Q&A of likely evaluation
questions with answers you can say out loud.**

You do **not** need any prior Blender knowledge to follow this. Every term is
explained the first time it appears.

---

## 0. The 30-second summary (say this if asked "what is your project?")

> "It's a 3-D domino chain-reaction animation made in Blender. About 450
> coloured dominoes are arranged on a wooden table in a room. The first
> domino is tipped, and a chain reaction runs through curves, a zig-zag, a
> loop, up a staircase, across a bridge, then it releases a rolling **marble**,
> the marble triggers a **seesaw**, the seesaw launches the next domino, and
> the chain finishes by spelling the letters **C G**. The falling is real
> **physics** (Blender's Rigid Body simulation), and one camera slowly
> follows the whole thing. It renders to a 59-second 1080p video."

---

## 1. What actually happens in the video (the timeline)

The animation is **1411 frames** long at **24 frames per second = 58.8 seconds**.
Blender measures time in **frames** (still images); 24 of them played per
second make smooth motion.

| Time | Frame | What happens on screen |
|---|---|---|
| 0–6 s | 1–144 | Wide "establishing" shot of the whole table. Nothing moves yet. |
| ~6.6 s | 159 | The **first domino tips over** (lead-in row). Chain starts. |
| 7.6 s | 183 | Runs through the **S-curve** (red dominoes). |
| 9.1 s | 219 | Through the **zig-zag** (yellow). |
| 13 s | 313 | Around the **circular loop** (green). |
| 15.6 s | 375 | Up the **staircase** (7 steps, blue). |
| 17.4 s | 417 | Across the **bridge** between two platforms (orange). |
| 21.6 s | 519 | A domino nudges the **steel marble** into its chute. |
| 22 s | 529 | The marble hits the next row → the **seesaw** trigger. |
| 22.2 s | 533 | Seesaw tips → **launches the payload domino**. |
| 27 s | 647 | Into the **spiral** (rainbow dominoes). |
| 30.9 s | 741 | A tall **"crossover"** domino hops the chain over an already-fallen lane. |
| 35.5 s | 851 | Starts drawing the letter **C** (red). |
| 43 s | 1031 | Starts drawing the letter **G** (blue). |
| 46.8 s | 1123 | **Last domino falls** — "CG" is fully revealed. |
| 46.8–58.8 s | 1123–1411 | Camera **holds** on the finished "CG" for ~12 s, then ends. |

These exact numbers are stored **inside the .blend file** in a text block
called **`SIM_NOTES`** (see section 9 on how to read it). Handy to quote.

---

## 2. Blender in 5 minutes (so you can navigate during the demo)

When you open `domino_chain_reaction.blend`, the screen is split into
**editors** (panels). The ones that matter:

- **3-D Viewport** (the big middle area) — the 3-D world. You orbit around it
  by holding the **middle mouse button** and dragging; zoom with the scroll
  wheel; pan with **Shift + middle mouse**.
- **Timeline** (bottom strip with numbers) — the frames. Press **Spacebar**
  to play the animation. Drag the blue marker to scrub through time.
- **Outliner** (top-right list) — a folder tree of **every object** in the
  scene, grouped into **Collections** (like folders). This is where you point
  when the examiner asks "where is X?".
- **Properties editor** (bottom-right, column of little tab icons) — all the
  settings. The tabs you'll use:
  - 🎥 **Render Properties** — which render engine (Cycles/Eevee), samples.
  - 🖨 **Output Properties** — resolution, frame rate, video format.
  - 🌐 **Scene Properties** — contains the **Rigid Body World** (the physics).
  - 🔧 **Physics Properties** — per-object physics (rigid body settings).
  - 🔴 **Material Properties** — the colour/surface of the selected object.
  - 🎞 **Object Constraint Properties** — the camera's "look-at" and the
    seesaw hinge live here / in Physics.

**Click any object** in the Outliner (or in the viewport) to *select* it; its
settings then appear in the Properties editor. Selected objects get an
orange outline.

---

## 3. The scene, collection by collection

Everything is organised into **Collections** (Blender's folders), visible in
the Outliner. This organisation is itself a grading point ("well organised
scene"). There are **6 collections you made** plus 2 that Blender creates
automatically for physics.

### 3.1 `Environment` (21 objects) — the room and table
- **`Floor`** — a big flat box, wood-textured.
- **`Wall_North`, `Wall_West`, `Wall_South`** — three plain walls.
- **`Wall_East_*`** (5 pieces) — the fourth wall, built in pieces so it has a
  **window hole** in it (light comes through here).
- **`WindowFrame_*`** (6 thin bars) — the window frame and its cross bars.
- **`Table_Top`** — the polished walnut table surface (3.6 m × 2.1 m).
- **`Table_Leg_1..4`** and **`Table_Apron_*`** — the four legs and side rails.

The **table top and floor are "Passive" rigid bodies** (see section 4) — solid
things the dominoes rest on and collide with, but that never move themselves.

### 3.2 `Dominoes` (452 objects) — the stars of the show
- Named **`Domino_0001_lead_in`**, `Domino_0002_lead_in`, … up to the letters,
  and one special **`Domino_Seesaw_Payload`**.
- The suffix (`_lead_in`, `_s_curve`, `_zigzag`, `_circle`, `_stairs`,
  `_bridge`, `_after_marble`, `_spiral`, `_crosser`, `_letter_C`, `_letter_G`,
  …) tells you **which part of the run** each domino belongs to — useful when
  the examiner asks "which dominoes make the C?" → the ones ending `_letter_C`.
- Each domino is **50 mm tall × 24 mm wide × 8 mm thick** with slightly
  **rounded (bevelled) edges**, like a real plastic domino.
- Seven colours: **white, black, red, blue, yellow, green, orange**. Different
  sections use different colours so the path reads clearly.
- Every domino is an **"Active" rigid body** — it obeys gravity and can be
  knocked over.

### 3.3 `Props` (24 objects) — the mechanisms and supports
- **`Stairs_Step_1..7`** — a 7-step staircase the dominoes climb.
- **`Platform_A`, `Platform_B`** — raised platforms at the top of the stairs.
- **`Bridge_Deck`, `Bridge_Leg_1/2`, `Bridge_Rail_±1`** — a little wooden
  bridge/ramp connecting the two platforms.
- **`Chute_Floor`, `Chute_Rail_±1`** — an inclined ramp (a "chute") the marble
  rolls down.
- **`Marble`** — a shiny **steel ball** (radius 12.5 mm). An **Active** rigid
  body, sphere-shaped, so it *rolls*.
- **`Runway_Rail_±1`** — low rails that keep the marble travelling straight.
- **`Seesaw_Stand`** — the pivot post the seesaw balances on.
- **`Seesaw_Plank`** — the see-saw beam itself (this one **rotates**).
- **`Seesaw_Stop`** — a small block the plank rests on at the start.
- **`Payload_Stand`** — a tiny platform holding the domino the seesaw launches.

### 3.4 `Lights` (2 objects) — see section 6.
### 3.5 `Camera` (2 objects) — see section 7.
### 3.6 `Physics` (1 object) — **`Seesaw_Hinge`**, the pivot constraint (section 5).
### 3.7 Auto groups: `RigidBodyWorld` / `RigidBodyConstraints`
Blender makes these automatically to hold all physics objects. You didn't
create them by hand; don't worry about them.

---

## 4. The big concept: **Rigid Body Physics** (this is the heart of the project)

**What it is:** Instead of animating each domino falling by hand (impossible
for 450), we let Blender's built-in physics engine (called **Bullet**)
calculate it. You tell Blender "these objects are solid and have weight," and
it works out how they collide, tip, and tumble under **gravity** — exactly
like the real world.

Every object that takes part in physics has a **Rigid Body** setting, of one
of two types:

- **Active** — it moves: affected by gravity and collisions. All **dominoes**,
  the **marble**, and the **seesaw plank** are Active.
- **Passive** — it's solid but never moves on its own: things *collide with* it.
  The **table, floor, stairs, platforms, bridge, chute, seesaw stand** are
  Passive.

Each rigid body also has a **Collision Shape** — the invisible shape Blender
uses for collision maths:
- Dominoes use a **Box** shape (fast and accurate for a cuboid).
- The marble uses a **Sphere** (so it can roll).
- The wooden props use a **Convex Hull** (a shape that wraps the mesh).

And physical properties: **Mass** (a domino ≈ 20 g, the marble ≈ 35 g),
**Friction** (grip), and **Restitution** (bounciness — kept low so dominoes
don't bounce unrealistically).

### Baking — the most important word for your evaluation
Physics is normally re-calculated live, which is slow and can change slightly
each time. **Baking** means: run the whole simulation once and **save the
result** (every object's position on every frame) *into the file*. After
baking, the animation plays back instantly and is **identical every time** —
essential for rendering. Our file is **already baked** (1–1700 frames of
cache stored inside the .blend).

> If asked "did you bake it?" → **"Yes. I ran the Rigid Body simulation and
> baked it to the cache, so the fall is locked in and renders consistently."**

**Where it lives in the app:** *Scene Properties → Rigid Body World*. Settings
we used: **Speed (time scale) = 0.45** (plays the physics at 45% speed — a
gentle slow-motion that looks "satisfying"), **Steps per Second / substeps =
30** and **Solver Iterations = 20** (higher = more accurate, stops dominoes
passing through each other), and the **Cache → Bake** button.

---

## 5. The three special mechanisms (examiners love these)

### 5.1 The Marble Track
A domino on the last platform tips over and **pushes a steel marble** off the
edge. The marble (a Sphere rigid body) **rolls down the inclined chute**,
guided by side rails, reaches the table, and **knocks over the next domino**,
continuing the chain. It demonstrates rolling physics and one type of energy
transfer (falling domino → rolling ball → falling domino).

### 5.2 The Seesaw (uses a **Hinge Constraint**)
A **constraint** is a rule that limits how an object can move. The
**`Seesaw_Hinge`** is a **Hinge** constraint: it pins the **`Seesaw_Plank`** so
it can **only rotate about one axis**, like a real see-saw on a pivot.

How it works in the video: an incoming domino falls onto one end (the *input
arm*) of the plank. That end drops, so the **other end swings up** and flicks
the **payload domino** (which was standing on `Payload_Stand`) forward onto the
next domino. This is the classic "one side pushes the other side" seesaw the
brief asked for.

**Where it lives:** select `Seesaw_Hinge` → *Physics Properties → Rigid Body
Constraint → Type: Hinge*. It links two objects: `object1 = Seesaw_Stand`
(the fixed pivot) and `object2 = Seesaw_Plank` (the moving beam).

### 5.3 The Crossover (`_crosser` domino)
At one spot the path has to **cross over a lane that has already fallen**
(the spiral's entrance). A single **double-height domino** is placed there;
when it topples it's tall enough to **reach across the flattened dominoes** and
start the chain again on the far side. It's a neat trick to make two paths
intersect without one blocking the other.

---

## 6. Lighting

Two lights (in the `Lights` collection):

- **`Sun_Key`** — a **Sun** light (energy 5.5). A Sun light shines parallel
  rays from one direction, like real sunlight, regardless of distance. Ours is
  angled to come **through the window**, giving warm daylight and soft shadows.
- **`Area_Fill`** — an **Area** light (150 W), a soft rectangular light above
  the table. "Fill" light gently brightens the shadows so nothing is pitch
  black. Big area lights = **soft shadows** (nicer, less harsh).

> The brief asked for "one Sun, one Area light, soft shadows, no HDRIs" — that's
> exactly this. (An **HDRI** is a 360° photo used to light a scene; we
> deliberately didn't use one, to keep it simple.)

**Where it lives:** select a light → *Object Data (Light) Properties* → Type,
Colour, Power/Strength.

---

## 7. The Camera

Two objects in the `Camera` collection:

- **`Camera_Main`** — the actual camera. **32 mm lens** (a fairly wide view),
  with **Depth of Field (DoF)** available (a photographic blur that softly
  defocuses the background).
- **`Focus_Target`** — an **Empty** (an invisible helper object — it has a
  position but no surface and never renders). The camera is told to **always
  point at this Empty** using a **"Track To" constraint**. To move the camera's
  gaze, we move the Empty; the camera automatically turns to follow it.

**The camera move is animated with keyframes.** A **keyframe** stores a value
(here, a position) at a specific frame; Blender smoothly **interpolates**
(fills in) the frames between. The camera has **51 position keyframes** that
make it: start wide → slowly move in and follow the falling wave → pause near
the marble mechanism → follow on → rise up over the letters → hold on "CG".
It's **one continuous camera** (no cuts), as the brief required.

> If asked "how did you animate the camera?" → **"With keyframes. I set the
> camera's position at key moments and Blender interpolates between them. It
> aims at an Empty via a Track-To constraint, so I animate where it looks by
> moving that Empty."**

**Where it lives:** select the camera → the keyframes show as diamonds in the
Timeline. Camera settings: *Object Data (Camera) Properties* → Focal Length,
Depth of Field.

---

## 8. Materials (the colours and surfaces)

A **material** defines how a surface looks: its colour, shininess, metalness,
etc. Blender's default material node is the **Principled BSDF** — one node with
sliders for **Base Color**, **Roughness** (0 = mirror-smooth/glossy, 1 = matte),
**Metallic** (0 = plastic/wood, 1 = metal), and **Coat** (a clear glossy
lacquer layer). Our 13 materials:

| Material | Used on | Look |
|---|---|---|
| `Mat_Domino_red/blue/green/yellow/orange/white/black` | dominoes | coloured **plastic** — smooth, slight clear coat |
| `Mat_Table_Walnut` | table | dark **polished wood**, glossy coat |
| `Mat_Floor_Oak` | floor | lighter **wood** floor |
| `Mat_Prop_Birch` | stairs, bridge, seesaw, chute | plain light **wood** |
| `Mat_Marble_Steel` | marble | **metal** (Metallic = 1, very smooth → shiny) |
| `Mat_Wall` | walls | flat off-white paint |
| `Mat_WindowFrame` | window frame | white frame |

The wood materials are **procedural** — the grain is generated by math
(a **Wave texture** distorted by a **Noise texture** feeding a **Color Ramp**),
not a photo. Procedural = no image files needed, so the .blend is
self-contained.

> If asked "how did you make the wood?" → **"Procedurally, with a Wave texture
> for the grain plus a Noise texture for variation, mapped through a Colour
> Ramp into the Base Colour of a Principled BSDF."**

**Where it lives:** select an object → *Material Properties* (the red sphere
tab). To see the node network: switch an editor to the **Shading** workspace
(top tab bar).

---

## 9. Reading the built-in notes (`SIM_NOTES`)

Inside the file there's a text note listing every trigger frame. To see it:
in the top tab bar switch to the **Scripting** workspace (or change any editor
to a **Text Editor**), then open the **`SIM_NOTES`** datablock from the text
dropdown. Quoting these frame numbers in the viva shows you understand the
timing.

---

## 10. How each part is made **by hand in the Blender app**

*(We generated the file with a Python script for precision, but this is the
equivalent manual workflow — describe it this way in the evaluation, because
it's what "doing it in Blender" means. Every step below is a real GUI action.)*

**A. Make one domino**
1. `Shift + A → Mesh → Cube` (adds a cube).
2. In the **N-panel** (press `N`) or with `S` (scale), size it to 50×24×8 mm.
3. `Ctrl + B` (Bevel), drag, to round the edges.
4. *Material Properties → New*, set **Base Color** and Roughness → a coloured
   plastic.

**B. Lay out ~450 dominoes along the path**
- Duplicate with `Shift + D` and place each one, or use an **Array modifier**
  along a **curve** for the straight/curved runs, spacing them ~33 mm apart and
  rotating each to follow the path. (The script automated exactly this spacing
  and rotation; by hand you'd duplicate-and-place in rows.)

**C. Build the room and table**
- More cubes, scaled into a floor, walls, table top and legs. Give them wood
  materials. For the window, cut a hole (model the wall in pieces around the
  opening, as we did).

**D. Build the props**
- Stairs = 7 cubes of increasing height. Bridge, platforms, chute = scaled
  cubes. Marble = `Shift + A → Mesh → UV Sphere`. Seesaw = a thin cube (plank)
  on a small post (stand).

**E. Turn on physics**
1. Select all dominoes → *Object → Rigid Body → Add Active* (or Physics
   Properties → Rigid Body). Set **Box** shape, mass ≈ 20 g.
2. Select the marble → Add Active, **Sphere** shape.
3. Select table/floor/stairs/etc. → *Add Passive*.
4. **Seesaw hinge:** select the plank, then `Shift + A → Empty` at the pivot;
   select the empty → *Physics → Rigid Body Constraint → Hinge*, and set its
   two objects to the stand and the plank.

**F. Set gravity & bake**
- *Scene Properties → Rigid Body World*: set **Speed 0.45**, **Substeps 30**,
  **Solver Iterations 20**, cache end frame.
- Tip the first domino: give it a tiny starting rotation with two **keyframes**
  (upright, then leaning), then let physics take over.
- *Rigid Body World → Cache → **Bake***. Wait — it computes the whole fall.

**G. Lights**
- `Shift + A → Light → Sun`; angle it through the window; set power.
- `Shift + A → Light → Area`; place above table; set power 150.

**H. Camera**
- `Shift + A → Camera`. Add an **Empty** as the look target. On the camera:
  *Constraints → Add → Track To → target = the Empty*.
- Enable **auto-keyframe**, step through time, move the camera + Empty at key
  moments → creates the keyframes. Blender interpolates the smooth move.

**I. Organise into Collections**
- In the Outliner, make collections `Environment, Dominoes, Props, Lights,
  Camera, Physics`; select objects and press **`M`** to move them in.

**J. Render settings & export**
- *Render Properties → Cycles*, samples 128, denoise on.
- *Output Properties → 1920×1080, 24 fps, FFMPEG / MPEG-4 / H.264*.
- *Render → Render Animation* → produces the MP4.

---

## 11. Opening and rendering (quick recap)

1. Open `domino_chain_reaction.blend` in Blender (5.x).
2. Press **Spacebar** to watch the baked animation.
3. To render the video: *Render → Render Animation* (`Ctrl + F12`). Output
   MP4 goes to a `render/` folder next to the file.
4. On a GPU (your office RTX 5090): *Edit → Preferences → System → Cycles
   Render Devices → OptiX → tick the GPU*, then *Render Properties → Device →
   GPU Compute*. Full render ≈ 20–45 min (vs ~3 days on a laptop CPU).

The engine is **Cycles** (a physically-accurate **ray tracer** — realistic
light, slower). The alternative, **Eevee**, is a faster **rasteriser** (good
for previews). The reference `domino_chain_reaction.mp4` in this folder was
made with Eevee for speed; Cycles gives crisper reflections/shadows.

---

## 12. Evaluation Q&A — likely questions & answers to say

**Q: What is a rigid body?**
A: A solid object the physics engine can move and collide. *Active* ones fall
and get knocked over (dominoes, marble); *Passive* ones stay put but block
things (table, floor, stairs).

**Q: How do the dominoes fall without you animating each one?**
A: They're Active rigid bodies. I tip only the first one; Blender's Bullet
physics engine calculates every collision and topple from gravity.

**Q: What does "baking" mean and why do it?**
A: Baking runs the simulation once and stores every object's position per
frame inside the file, so playback is instant and identical every render.

**Q: Why is it in slow motion?**
A: The Rigid Body World **Speed** is 0.45, so physics runs at 45% speed — it
looks smoother and more satisfying, and reads clearly on camera.

**Q: How does the seesaw work?**
A: A **Hinge constraint** lets the plank rotate on one axis. A domino falls on
one end, that end drops, the far end swings up and launches the payload domino.

**Q: How does the marble keep the chain going?**
A: A domino pushes it off a platform; as a Sphere rigid body it rolls down the
chute and knocks the next domino — energy passed from falling to rolling to
falling.

**Q: How is the camera animated?**
A: With keyframes on its position at key moments; Blender interpolates between
them for one smooth continuous move. It aims via a Track-To constraint at an
Empty I animate.

**Q: What lights did you use?**
A: One Sun light through the window for warm daylight, and one soft Area light
above the table as fill — giving soft shadows. No HDRI.

**Q: What are collections?**
A: Blender's folders in the Outliner. I grouped objects into Environment,
Dominoes, Props, Lights, Camera and Physics so the scene is organised.

**Q: Cycles vs Eevee?**
A: Cycles is a ray tracer — physically accurate light, slower, used for the
final render. Eevee is real-time rasterisation — much faster, used for
previews.

**Q: What are the materials?**
A: Principled BSDF surfaces. Dominoes are coloured plastic (low roughness,
slight coat); the marble is metal (Metallic = 1); wood is procedural (Wave +
Noise textures through a Colour Ramp).

**Q: How many dominoes / how long / what resolution?**
A: 452 dominoes; 1411 frames at 24 fps = 58.8 seconds; 1920×1080 (Full HD).

**Q: How would you make it 2 minutes?**
A: Lower the Rigid Body **Speed** for slower motion, but the dominoes are
"start-deactivated," so too slow starves later collisions of energy and the
chain stalls — so you'd also lower each domino's deactivation threshold. We
kept it reliable over long, which the brief asked for.

---

## 13. Mini-glossary

- **Frame** — one still image; 24 per second make the video.
- **Mesh** — the 3-D shape of an object (its vertices/faces).
- **Rigid Body** — an object controlled by the physics engine.
- **Active / Passive** — moves under physics / stays put but is solid.
- **Collision Shape** — the simple shape (Box/Sphere/Convex Hull) used for
  collision maths.
- **Bake / Cache** — pre-computing and storing the simulation.
- **Constraint** — a rule limiting motion (Hinge = rotate on one axis;
  Track-To = always face a target).
- **Keyframe** — a stored value at a frame; Blender interpolates between them.
- **Empty** — an invisible helper object (position only, never rendered).
- **Material / Principled BSDF** — how a surface looks (colour, roughness,
  metallic, coat).
- **Procedural texture** — a pattern generated by math, not an image.
- **Collection** — a folder for organising objects (Outliner).
- **Cycles / Eevee** — the two render engines (ray tracer / real-time).
- **Render / Bake are different!** — *Bake* = compute the physics; *Render* =
  turn the 3-D scene into the final images/video.
- **Sun / Area light** — directional daylight / soft rectangular light.
- **Depth of Field** — camera background blur for a photographic look.
- **HDRI** — a 360° image used to light a scene (we did **not** use one).

---

*File made in Blender 5.x. Scene generated by `generate_domino_scene.py`,
simulation baked, and organised into collections. Everything above describes
what is actually in `domino_chain_reaction.blend`.*
