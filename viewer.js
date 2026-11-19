/* Local GLB 2.0 viewer for the eight static Blender portraits. */
(() => {
  'use strict';

  const instances = new WeakMap();
  const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const radians = Math.PI / 180;
  const clamp = (value, low, high) => Math.max(low, Math.min(value, high));

  function multiply(left, right) {
    const result = new Float32Array(16);
    for (let col = 0; col < 4; col++) {
      for (let row = 0; row < 4; row++) {
        for (let k = 0; k < 4; k++) {
          result[col * 4 + row] += left[k * 4 + row] * right[col * 4 + k];
        }
      }
    }
    return result;
  }

  function nodeMatrix(node) {
    if (node.matrix) return node.matrix;
    const [x, y, z, w] = node.rotation || [0, 0, 0, 1];
    const [a, b, c] = node.scale || [1, 1, 1];
    const t = node.translation || [0, 0, 0];
    return [
      (1 - 2 * (y * y + z * z)) * a, 2 * (x * y + z * w) * a, 2 * (x * z - y * w) * a, 0,
      2 * (x * y - z * w) * b, (1 - 2 * (x * x + z * z)) * b, 2 * (y * z + x * w) * b, 0,
      2 * (x * z + y * w) * c, 2 * (y * z - x * w) * c, (1 - 2 * (x * x + y * y)) * c, 0,
      t[0], t[1], t[2], 1
    ];
  }

  function normalMatrix(m) {
    // Inverse transpose of the linear part, including Blender's nonuniform node scales.
    const [a,b,c,,d,e,f,,g,h,i] = m;
    const cof = [e*i-f*h, f*g-d*i, d*h-e*g, h*c-i*b, i*a-g*c, g*b-h*a, b*f-c*e, c*d-a*f, a*e-b*d];
    const determinant = a*cof[0] + b*cof[1] + c*cof[2];
    return new Float32Array(cof.map(value => value / (determinant || 1)));
  }

  function parseGLB(bytes) {
    const header = new DataView(bytes);
    if (header.byteLength < 20 || header.getUint32(0, true) !== 0x46546c67 ||
        header.getUint32(4, true) !== 2 || header.getUint32(8, true) !== header.byteLength) {
      throw new Error('模型包格式无效。');
    }
    let json, binary;
    for (let offset = 12; offset + 8 <= bytes.byteLength;) {
      const length = header.getUint32(offset, true);
      const type = header.getUint32(offset + 4, true);
      offset += 8;
      if (offset + length > bytes.byteLength) throw new Error('模型数据不完整。');
      if (type === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(new Uint8Array(bytes, offset, length)));
      if (type === 0x004e4942) binary = new DataView(bytes, offset, length);
      offset += length;
    }
    if (!json || !binary) throw new Error('模型缺少场景或几何数据。');
    return {json, binary};
  }

  const componentTypes = {
    5120: [1, 'getInt8', 127], 5121: [1, 'getUint8', 255], 5122: [2, 'getInt16', 32767],
    5123: [2, 'getUint16', 65535], 5125: [4, 'getUint32', 4294967295], 5126: [4, 'getFloat32', 1]
  };

  function readAttribute(scene, index, type, outType = Float32Array) {
    const a = scene.json.accessors[index];
    const view = scene.json.bufferViews[a.bufferView];
    const format = componentTypes[a.componentType];
    const count = type === 'VEC3' ? 3 : 1;
    if (a.type !== type || !format || !view || (view.buffer || 0) !== 0 || a.sparse) {
      throw new Error('模型属性格式暂不支持。');
    }
    const stride = view.byteStride || count * format[0];
    const start = (view.byteOffset || 0) + (a.byteOffset || 0);
    const result = new outType(a.count * count);
    let out = 0;
    for (let row = 0; row < a.count; row++) {
      const pos = start + row * stride;
      for (let col = 0; col < count; col++) {
        const v = scene.binary[format[1]](pos + col * format[0], true);
        result[out++] = a.normalized ? Math.max(-1, v / format[2]) : v;
      }
    }
    return result;
  }

  function vertexNormals(positions, indices) {
    const normals = new Float32Array(positions.length);
    const count = indices ? indices.length : positions.length / 3;
    for (let k = 0; k + 2 < count; k += 3) {
      const a = 3 * (indices ? indices[k] : k);
      const b = 3 * (indices ? indices[k + 1] : k + 1);
      const c = 3 * (indices ? indices[k + 2] : k + 2);
      const ux = positions[b] - positions[a], uy = positions[b + 1] - positions[a + 1], uz = positions[b + 2] - positions[a + 2];
      const vx = positions[c] - positions[a], vy = positions[c + 1] - positions[a + 1], vz = positions[c + 2] - positions[a + 2];
      const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      for (const j of [a,b,c]) { normals[j] += nx; normals[j+1] += ny; normals[j+2] += nz; }
    }
    return normals;
  }

  function extent(positions) {
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < positions.length; i++) {
      const axis = i % 3;
      min[axis] = Math.min(min[axis], positions[i]);
      max[axis] = Math.max(max[axis], positions[i]);
    }
    return {min, max};
  }

  function prepareScene(scene, gl, makeBuffer) {
    const {json} = scene;
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    const shared = new Map(), draws = [];
    const supportsUint32 = Boolean(gl.getExtension('OES_element_index_uint'));
    function geometry(primitive) {
      if (shared.has(primitive)) return shared.get(primitive);
      const positions = readAttribute(scene, primitive.attributes.POSITION, 'VEC3');
      const vertices = positions.length / 3;
      if (!vertices) throw new Error('模型没有可显示的顶点。');
      let indices = null;
      if (primitive.indices != null) {
        const source = json.accessors[primitive.indices].componentType;
        const Index = {5121: Uint8Array, 5123: Uint16Array, 5125: Uint32Array}[source];
        if (!Index) throw new Error('三角面索引无效。');
        indices = readAttribute(scene, primitive.indices, 'SCALAR', Index);
        if (indices.some(i => i >= vertices)) throw new Error('三角面超出模型范围。');
      }
      const normals = primitive.attributes.NORMAL == null ? vertexNormals(positions, indices)
        : readAttribute(scene, primitive.attributes.NORMAL, 'VEC3');
      // WebGL 1 devices without uint indices can render the same triangles unindexed.
      const expand = indices instanceof Uint32Array && !supportsUint32;
      const count = indices ? indices.length : vertices;
      const interleaved = new Float32Array((expand ? count : vertices) * 6);
      for (let i = 0; i < interleaved.length / 6; i++) {
        const n = (expand ? indices[i] : i) * 3;
        for (let axis = 0; axis < 3; axis++) {
          interleaved[6*i+axis] = positions[n+axis];
          interleaved[6*i+3+axis] = normals[n+axis];
        }
      }
      const record = {bounds: extent(positions), vertices: makeBuffer(gl.ARRAY_BUFFER, interleaved),
        indices: indices && !expand ? makeBuffer(gl.ELEMENT_ARRAY_BUFFER, indices) : null,
        type: indices ? {1:gl.UNSIGNED_BYTE,2:gl.UNSIGNED_SHORT,4:gl.UNSIGNED_INT}[indices.BYTES_PER_ELEMENT] : null,
        count};
      shared.set(primitive, record);
      return record;
    }
    function walk(index, parent) {
      const node = json.nodes[index];
      const world = multiply(parent, nodeMatrix(node));
      if (node.mesh != null) {
        for (const primitive of json.meshes[node.mesh].primitives) {
          if (primitive.mode != null && primitive.mode !== 4) continue;
          const item = geometry(primitive);
          const {bounds} = item;
          for (const x of [bounds.min[0],bounds.max[0]]) for (const y of [bounds.min[1],bounds.max[1]]) {
            for (const z of [bounds.min[2],bounds.max[2]]) for (let axis = 0; axis < 3; axis++) {
              const n = world[axis]*x + world[axis+4]*y + world[axis+8]*z + world[axis+12];
              min[axis] = Math.min(min[axis], n); max[axis] = Math.max(max[axis], n);
            }
          }
          const mat = json.materials?.[primitive.material];
          const base = mat?.pbrMetallicRoughness?.baseColorFactor || [.77,.72,.62,1];
          draws.push({item, world, normals: normalMatrix(world), color: base.slice(0,3),
            roughness: mat?.pbrMetallicRoughness?.roughnessFactor ?? 1});
        }
      }
      for (const child of node.children || []) walk(child, world);
    }
    const active = json.scenes?.[json.scene || 0];
    if (!active) throw new Error('模型缺少可显示的场景。');
    for (const root of active.nodes || []) walk(root, identity);
    if (!draws.length || !min.every(Number.isFinite)) throw new Error('模型中没有可显示的三角面。');
    return {draws, center: min.map((v,i) => (v+max[i])/2), size: min.map((v,i) => Math.max(.0001, max[i]-v))};
  }

  const vertexSource = `
    attribute vec3 aPosition, aNormal;
    uniform mat4 uWorld;
    uniform mat3 uNormals, uTurn;
    uniform vec3 uCenter, uFit;
    varying mediump vec3 vNormal;
    void main() {
      vec3 p = uTurn * ((uWorld * vec4(aPosition,1.0)).xyz - uCenter);
      gl_Position = vec4(p * uFit, 1.0);
      vNormal = normalize(uTurn * uNormals * aNormal);
    }`;
  const fragmentSource = `
    precision mediump float;
    varying mediump vec3 vNormal;
    uniform vec3 uColor;
    uniform float uRoughness;
    void main() {
      vec3 n = normalize(vNormal);
      vec3 key = normalize(vec3(-0.55, 0.78, 0.68));
      float direct = clamp((dot(n,key)+.25)/1.25,0.0,1.0);
      float face = max(dot(n,vec3(0.0,0.0,1.0)),0.0);
      float sky = 0.5+0.5*n.y;
      vec3 diffuse = uColor * (vec3(.52,.50,.50) + vec3(.11)*sky + vec3(.52,.49,.46)*direct);
      float gloss = pow(max(dot(n,normalize(key+vec3(0.0,0.0,1.0))),0.0),mix(50.0,9.0,uRoughness));
      float finish = .043 * (1.0-uRoughness)*(1.0-uRoughness)+.002;
      vec3 light = diffuse + finish*gloss + vec3(.002)*pow(1.0-face,3.0);
      gl_FragColor = vec4(pow(clamp(light,0.0,1.0),vec3(1.0/2.2)),1.0);
    }`;

  function mount(canvas, {src, onReady, onError} = {}) {
    instances.get(canvas)?.dispose();
    const controller = new AbortController();
    const buffers = [], shaders = [];
    const original = {tabindex: canvas.getAttribute('tabindex'), touch: canvas.style.touchAction, cursor: canvas.style.cursor};
    let program, gl, locations, model, frame, observer, pointer;
    let closed = false, yaw = 0, pitch = 0.045, magnification = 1;

    function draw() {
      frame = 0;
      if (!model || closed) return;
      const bounds = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, Math.round(bounds.width * ratio)), h = Math.max(1, Math.round(bounds.height * ratio));
      if (canvas.width !== w) canvas.width = w;
      if (canvas.height !== h) canvas.height = h;
      gl.viewport(0,0,w,h);
      gl.clearColor(0,0,0,0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE); gl.disable(gl.BLEND);
      gl.useProgram(program);
      const aspect = w/h, [dx,dy,dz] = model.size;
      const half = .55 * Math.max(dy, Math.max(dx,dz)/aspect);
      const sy = Math.sin(yaw), cy = Math.cos(yaw), sp = Math.sin(pitch), cp = Math.cos(pitch);
      gl.uniformMatrix3fv(locations.uTurn, false, [cy,sp*sy,-cp*sy,0,cp,sp,sy,-sp*cy,cp*cy]);
      gl.uniform3fv(locations.uCenter, model.center);
      gl.uniform3fv(locations.uFit, [magnification/(half*aspect),magnification/half,-1/Math.hypot(dx,dy,dz)]);
      gl.enableVertexAttribArray(locations.aPosition); gl.enableVertexAttribArray(locations.aNormal);
      for (const {item, world, normals, color, roughness} of model.draws) {
        gl.uniformMatrix4fv(locations.uWorld,false,world);
        gl.uniformMatrix3fv(locations.uNormals,false,normals);
        gl.uniform3fv(locations.uColor,color);
        gl.uniform1f(locations.uRoughness,roughness);
        gl.bindBuffer(gl.ARRAY_BUFFER,item.vertices);
        gl.vertexAttribPointer(locations.aPosition,3,gl.FLOAT,false,24,0);
        gl.vertexAttribPointer(locations.aNormal,3,gl.FLOAT,false,24,12);
        if (item.indices) {
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,item.indices);
          gl.drawElements(gl.TRIANGLES,item.count,item.type,0);
        } else gl.drawArrays(gl.TRIANGLES,0,item.count);
      }
    }
    function invalidate() { if (!closed && model && !frame) frame = requestAnimationFrame(draw); }
    function dispose() {
      if (closed) return;
      closed = true;
      controller.abort();
      observer?.disconnect();
      if (frame) cancelAnimationFrame(frame);
      if (pointer && canvas.hasPointerCapture?.(pointer.id)) canvas.releasePointerCapture(pointer.id);
      if (gl) {
        for (const buffer of buffers) gl.deleteBuffer(buffer);
        gl.useProgram(null);
        if (program) gl.deleteProgram(program);
        for (const shader of shaders) gl.deleteShader(shader);
        gl.clearColor(0,0,0,0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      }
      if (original.tabindex === null) canvas.removeAttribute('tabindex');
      else canvas.setAttribute('tabindex',original.tabindex);
      canvas.style.touchAction = original.touch;
      canvas.style.cursor = original.cursor;
      model = null;
      if (instances.get(canvas) === api) instances.delete(canvas);
    }
    const api = {
      dispose,
      rotate(degrees) { if (Number.isFinite(degrees)) yaw = (yaw + degrees * radians) % (Math.PI*2); invalidate(); },
      zoom(factor) { if (Number.isFinite(factor) && factor > 0) magnification = clamp(magnification*factor,.65,2.8); invalidate(); },
      reset() { yaw = 0; pitch = .045; magnification = 1; invalidate(); }
    };
    instances.set(canvas,api);
    function fail(error) { if (!closed) { dispose(); onError?.(error); } }

    function makeBuffer(target, data) {
      const buffer = gl.createBuffer();
      if (!buffer) throw new Error('显存不足，无法加载模型。');
      buffers.push(buffer);
      gl.bindBuffer(target,buffer); gl.bufferData(target,data,gl.STATIC_DRAW);
      return buffer;
    }
    function bindInput() {
      const opts = {signal:controller.signal};
      if (original.tabindex === null) canvas.tabIndex = 0;
      canvas.style.touchAction = 'pan-y';
      canvas.style.cursor = 'grab';
      canvas.addEventListener('pointerdown', e => {
        if (!e.isPrimary || e.button !== 0) return;
        pointer = {id:e.pointerId,x:e.clientX,y:e.clientY};
        canvas.setPointerCapture(e.pointerId);
        canvas.style.cursor = 'grabbing';
      },opts);
      canvas.addEventListener('pointermove', e => {
        if (e.pointerId !== pointer?.id) return;
        api.rotate((e.clientX-pointer.x)*.6);
        pitch = clamp(pitch+(e.clientY-pointer.y)*.006,-.55,.55);
        pointer.x=e.clientX; pointer.y=e.clientY;
      },opts);
      const release = () => {pointer=null; canvas.style.cursor = 'grab';};
      for (const name of ['pointercancel','pointerup','lostpointercapture']) canvas.addEventListener(name,release,opts);
      canvas.addEventListener('keydown', e => {
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        if (e.key === 'ArrowLeft') api.rotate(-15);
        else if (e.key === 'ArrowRight') api.rotate(15);
        else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
          pitch = clamp(pitch+(e.key === 'ArrowUp' ? -.1 : .1),-.55,.55); invalidate();
        } else if (e.key === '+' || e.key === '=') api.zoom(1.15);
        else if (e.key === '-') api.zoom(1/1.15);
        else if (e.key === 'Home' || e.key === '0') api.reset();
        else return;
        e.preventDefault();
      },opts);
      canvas.addEventListener('wheel',e => {
        if (document.activeElement !== canvas || e.ctrlKey || e.metaKey) return;
        e.preventDefault();
        api.zoom(Math.exp(-Math.sign(e.deltaY)*.1));
      },{...opts,passive:false});
      canvas.addEventListener('webglcontextlost',e => { e.preventDefault(); fail(new Error('三维图形上下文已中断。')); },opts);
      if (window.ResizeObserver) { observer = new ResizeObserver(invalidate); observer.observe(canvas); }
      else window.addEventListener('resize',invalidate,opts);
    }

    async function load() {
      if (window.location.protocol === 'file:') throw new Error('请通过本地 HTTP 服务查看三维模型。');
      gl = canvas.getContext('webgl',{alpha:true,antialias:true,depth:true,premultipliedAlpha:true});
      if (!gl) throw new Error('此设备无法启用 WebGL。');
      bindInput();
      const response = await fetch(src,{signal:controller.signal});
      if (!response.ok) throw new Error('未能获取模型文件（HTTP '+response.status+'）。');
      const bytes = await response.arrayBuffer();
      if (closed) return;
      program = gl.createProgram();
      for (const [kind,source] of [[gl.VERTEX_SHADER,vertexSource],[gl.FRAGMENT_SHADER,fragmentSource]]) {
        const shader = gl.createShader(kind);
        shaders.push(shader); gl.shaderSource(shader,source); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) throw new Error('设备未能编译三维材质。');
        gl.attachShader(program,shader);
      }
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error('设备未能初始化三维场景。');
      locations = {};
      for (const name of ['aPosition','aNormal']) locations[name] = gl.getAttribLocation(program,name);
      for (const name of ['uWorld','uNormals','uTurn','uCenter','uFit','uColor','uRoughness']) locations[name] = gl.getUniformLocation(program,name);
      model = prepareScene(parseGLB(bytes),gl,makeBuffer);
      draw();
      if (gl.isContextLost() || gl.getError() !== gl.NO_ERROR) throw new Error('绘制三维模型失败。');
      onReady?.();
    }
    Promise.resolve().then(() => { if (!closed) return load(); }).catch(fail);
    return api;
  }
  window.YincaiViewer = Object.freeze({mount});
})();
