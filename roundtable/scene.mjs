import {WebGLRenderer, Scene, OrthographicCamera, PMREMGenerator, DirectionalLight,
  HemisphereLight, Mesh, PlaneGeometry, ShadowMaterial, PCFSoftShadowMap, Vector3,
  Spherical, Color, NeutralToneMapping, SRGBColorSpace, OrbitControls, GLTFLoader,
  RoomEnvironment} from './three-viewer.mjs';

export function createViewer(canvas, pose, select) {
  const renderer = new WebGLRenderer({canvas, antialias:true, powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1,2));
  renderer.outputColorSpace = SRGBColorSpace; renderer.toneMapping = NeutralToneMapping;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = PCFSoftShadowMap;
  const scene = new Scene();
  scene.background = new Color('#f3f0e8');
  const pmrem = new PMREMGenerator(renderer), studio = new RoomEnvironment();
  const environment = pmrem.fromScene(studio,.04);
  scene.environment = environment.texture; scene.environmentIntensity = .7;
  studio.dispose(); pmrem.dispose();
  scene.add(new HemisphereLight(0xfff9ee,0xb1bac0,1.05));
  const key = new DirectionalLight(0xfff8eb,2);
  key.position.set(-3,6,4); key.castShadow = true;
  Object.assign(key.shadow.camera,{left:-4,right:4,top:4,bottom:-4,near:.1,far:18});
  key.shadow.mapSize.set(1024,1024); key.shadow.normalBias = .008; scene.add(key);
  const floor = new Mesh(new PlaneGeometry(60,60),new ShadowMaterial({opacity:.14}));
  floor.rotation.x = -Math.PI/2; floor.position.y = -.005; floor.receiveShadow = true; scene.add(floor);
  const camera = new OrthographicCamera(-1,1,1,-1,.02,100);
  const controls = new OrbitControls(camera,canvas);
  controls.enablePan = false; controls.minZoom = .86; controls.maxZoom = 2.1;
  controls.minPolarAngle = .2; controls.maxPolarAngle = Math.PI*.49;
  const draw = () => {if (!canvas.hidden) renderer.render(scene,camera);};
  controls.addEventListener('change',draw);
  function resize() {
    if (canvas.hidden) return;
    const {width,height} = canvas.parentElement.getBoundingClientRect();
    if (!width || !height) return;
    const aspect = width/height, half = Math.max(pose.height,pose.width/aspect)/2;
    Object.assign(camera,{top:half,bottom:-half,left:-half*aspect,right:half*aspect});
    renderer.setSize(width,height,false); camera.updateProjectionMatrix(); draw();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(canvas.parentElement);
  const events = new AbortController();
  const listener = {signal:events.signal};
  function reset() {
    camera.position.fromArray(pose.eye); controls.target.fromArray(pose.target); camera.zoom=1;
    controls.update(); resize();
  }
  canvas.addEventListener('keydown', event => {
    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key)) return;
    event.preventDefault();
    if (event.key === 'Home') {reset(); return;}
    const sphere = new Spherical().setFromVector3(camera.position.clone().sub(controls.target));
    if(event.key === 'ArrowLeft') sphere.theta-=.12;
    if(event.key === 'ArrowRight') sphere.theta+=.12;
    if(event.key === 'ArrowUp') sphere.phi-=.12;
    if(event.key === 'ArrowDown') sphere.phi+=.12;
    sphere.phi = Math.min(controls.maxPolarAngle,Math.max(controls.minPolarAngle,sphere.phi));
    camera.position.copy(controls.target).add(new Vector3().setFromSpherical(sphere)); controls.update(); draw();
  },listener);
  // The orthographic picking ray is shared by the six rigid figures and the furniture.
  // Test the whole assembly so a figure behind the table cannot receive the click.
  const pickable = [];
  let pointerStart = null;
  canvas.addEventListener('pointerdown', event => {
    pointerStart = (event.isPrimary && event.button === 0) ? [event.clientX,event.clientY] : null;
  },listener);
  canvas.addEventListener('pointercancel', () => {pointerStart = null;},listener);
  canvas.addEventListener('pointerup', event => {
    const start = pointerStart;
    pointerStart = null;
    if (!start || Math.hypot(event.clientX-start[0],event.clientY-start[1])>5) return;
    const box = canvas.getBoundingClientRect();
    const origin = new Vector3(2*(event.clientX-box.left)/box.width-1,1-2*(event.clientY-box.top)/box.height,-1).unproject(camera);
    const ray = {origin, direction:camera.getWorldDirection(new Vector3())};
    const hits = [], query = {ray, near:0, far:camera.far-camera.near};
    for (const mesh of pickable) mesh.raycast(query,hits);
    hits.sort((a,b) => a.distance-b.distance);
    const target = hits[0]?.object.userData.bookRole;
    if (target) select(target);
  },listener);
  const materials = new Map();
  async function load() {
    const gltf = await new GLTFLoader().loadAsync(new URL('./assembly.glb', import.meta.url).href);
    scene.add(gltf.scene);
    gltf.scene.traverse(object => {
      if (object.isMesh) {
        object.castShadow=true; object.receiveShadow=true; pickable.push(object);
      }
      if (object.name.startsWith('folio-')) {
        object.traverse(part => {if (part.isMesh) part.userData.bookRole = 'book';});
      }
    });
    for (const role of Object.keys(pose.projectedActors)) {
      const actor = gltf.scene.getObjectByName('agent-'+role);
      if (!actor) continue;
      const copies = new Map();
      const copy = original => {
        if (!copies.has(original)) copies.set(original,original.clone());
        return copies.get(original);
      };
      actor.traverse(mesh => {
        if (mesh.isMesh) {
          mesh.userData.bookRole = role;
          mesh.material = Array.isArray(mesh.material) ? mesh.material.map(copy) : copy(mesh.material);
        }
      });
      materials.set(role,[...copies.values()].filter(material => material.color).map(material => [material,material.color.clone()]));
    }
  }
  function highlight(selected) {
    for (const [role,colors] of materials) {
      for (const [material,base] of colors) {
        material.color.copy(base);
        if (role !== selected) material.color.lerp(new Color('#a7a69c'),.23);
      }
    }
    draw();
  }
  function dispose() {
    events.abort();
    observer.disconnect();
    controls.dispose();
    floor.geometry.dispose();
    floor.material.dispose();
    environment.dispose();
    renderer.dispose();
  }
  return {load,reset,highlight,dispose};
}
