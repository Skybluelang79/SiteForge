import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Input,
  NgZone,
  OnDestroy,
  ViewChild,
  inject,
} from '@angular/core';
import * as THREE from 'three';

import { IconComponent } from './icon.component';

@Component({
  selector: 'sf-site-scene',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './site-scene.component.html',
  styleUrl: './site-scene.component.css',
})
export class SiteSceneComponent implements AfterViewInit, OnDestroy {
  @ViewChild('canvas', { static: true }) private canvasRef!: ElementRef<HTMLCanvasElement>;
  @Input() compact = false;
  @Input() showTags = true;

  private readonly zone = inject(NgZone);
  private renderer?: THREE.WebGLRenderer;
  private scene?: THREE.Scene;
  private camera?: THREE.PerspectiveCamera;
  private frame = 0;
  private resizeObserver?: ResizeObserver;
  private crane?: THREE.Group;
  private hook?: THREE.Group;
  private dust?: THREE.Points;
  private clock = new THREE.Clock();
  private disposed = false;

  private radius = 20;
  private theta = 0.82;
  private phi = 1.02;
  private autoRotate = true;
  private pointerDown = false;
  private lastX = 0;
  private lastY = 0;
  private lastInteraction = 0;
  private readonly reducedMotion =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  ngAfterViewInit(): void {
    this.zone.runOutsideAngular(() => {
      this.init();
      this.animate();
    });
  }

  ngOnDestroy(): void {
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.resizeObserver?.disconnect();
    const canvas = this.canvasRef?.nativeElement;
    canvas?.removeEventListener('pointerdown', this.onPointerDown);
    canvas?.removeEventListener('wheel', this.onWheel);
    window.removeEventListener('pointermove', this.onPointerMove);
    window.removeEventListener('pointerup', this.onPointerUp);
    document.removeEventListener('visibilitychange', this.onVisibility);
    if (this.scene) {
      this.scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        if (mesh.geometry) {
          mesh.geometry.dispose();
        }
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(material)) {
          material.forEach((item) => item.dispose());
        } else {
          material?.dispose();
        }
      });
    }
    this.renderer?.dispose();
  }

  reset(): void {
    this.radius = 20;
    this.theta = 0.82;
    this.phi = 1.02;
    this.autoRotate = true;
  }

  zoomIn(): void {
    this.radius = Math.max(10, this.radius - 2);
    this.lastInteraction = performance.now();
  }

  zoomOut(): void {
    this.radius = Math.min(32, this.radius + 2);
    this.lastInteraction = performance.now();
  }

  private init(): void {
    const canvas = this.canvasRef.nativeElement;
    const host = canvas.parentElement ?? canvas;
    const width = host.clientWidth || 640;
    const height = host.clientHeight || 420;

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(width, height, false);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.08;

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x070c16, 0.022);

    this.camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 120);
    this.updateCamera();

    this.buildEnvironment();
    this.buildTower();
    this.buildCrane();
    this.buildSite();
    this.buildDust();

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(host);

    canvas.addEventListener('pointerdown', this.onPointerDown);
    canvas.addEventListener('wheel', this.onWheel, { passive: false });
    window.addEventListener('pointermove', this.onPointerMove);
    window.addEventListener('pointerup', this.onPointerUp);
    document.addEventListener('visibilitychange', this.onVisibility);
  }

  private updateCamera(): void {
    if (!this.camera) {
      return;
    }
    const center = new THREE.Vector3(0, 3.4, 0);
    this.camera.position.set(
      center.x + this.radius * Math.sin(this.phi) * Math.sin(this.theta),
      center.y + this.radius * Math.cos(this.phi),
      center.z + this.radius * Math.sin(this.phi) * Math.cos(this.theta),
    );
    this.camera.lookAt(center);
  }

  private resize(): void {
    if (!this.renderer || !this.camera) {
      return;
    }
    const canvas = this.canvasRef.nativeElement;
    const host = canvas.parentElement ?? canvas;
    const width = host.clientWidth || 640;
    const height = host.clientHeight || 420;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  private buildEnvironment(): void {
    if (!this.scene) {
      return;
    }
    const hemi = new THREE.HemisphereLight(0x9dbbff, 0x0a0f1c, 0.9);
    this.scene.add(hemi);

    const sun = new THREE.DirectionalLight(0xfff1d6, 2.4);
    sun.position.set(14, 20, 10);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.near = 1;
    sun.shadow.camera.far = 60;
    sun.shadow.camera.left = -18;
    sun.shadow.camera.right = 18;
    sun.shadow.camera.top = 18;
    sun.shadow.camera.bottom = -18;
    sun.shadow.bias = -0.0008;
    this.scene.add(sun);

    const rim = new THREE.DirectionalLight(0x3b82f6, 1.2);
    rim.position.set(-12, 8, -12);
    this.scene.add(rim);

    const glow = new THREE.PointLight(0xf59e0b, 28, 26, 2);
    glow.position.set(-6, 10, -2);
    this.scene.add(glow);

    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(16, 64),
      new THREE.MeshStandardMaterial({ color: 0x0a1220, roughness: 0.92, metalness: 0.08 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);

    const grid = new THREE.GridHelper(32, 32, 0x1e3a5f, 0x122033);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.75;
    grid.position.y = 0.01;
    this.scene.add(grid);

    const kerb = new THREE.Mesh(
      new THREE.RingGeometry(10.6, 11, 64),
      new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.8 }),
    );
    kerb.rotation.x = -Math.PI / 2;
    kerb.position.y = 0.02;
    this.scene.add(kerb);
  }

  private buildTower(): void {
    if (!this.scene) {
      return;
    }
    const tower = new THREE.Group();
    const floorHeight = 0.92;
    const floors = 10;
    const width = 5.2;
    const depth = 4.4;
    const completed = 7;

    const slabMaterial = new THREE.MeshStandardMaterial({
      color: 0xcbd5e1,
      roughness: 0.62,
      metalness: 0.15,
    });
    const concreteMaterial = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.86,
      metalness: 0.1,
    });
    const glassMaterial = new THREE.MeshStandardMaterial({
      color: 0x38bdf8,
      roughness: 0.12,
      metalness: 0.6,
      transparent: true,
      opacity: 0.32,
    });
    const warmGlass = new THREE.MeshStandardMaterial({
      color: 0xfbbf24,
      emissive: 0xf59e0b,
      emissiveIntensity: 0.55,
      roughness: 0.4,
      metalness: 0.2,
    });
    const steelMaterial = new THREE.MeshStandardMaterial({
      color: 0x64748b,
      roughness: 0.5,
      metalness: 0.7,
    });

    for (let floor = 0; floor < floors; floor += 1) {
      const y = floor * floorHeight;
      const slab = new THREE.Mesh(new THREE.BoxGeometry(width, 0.12, depth), slabMaterial);
      slab.position.set(0, y + 0.06, 0);
      slab.castShadow = true;
      slab.receiveShadow = true;
      tower.add(slab);

      const isComplete = floor < completed;
      const columnMaterial = isComplete ? concreteMaterial : steelMaterial;
      const offsets: [number, number][] = [
        [-width / 2 + 0.22, -depth / 2 + 0.22],
        [width / 2 - 0.22, -depth / 2 + 0.22],
        [-width / 2 + 0.22, depth / 2 - 0.22],
        [width / 2 - 0.22, depth / 2 - 0.22],
      ];
      offsets.forEach(([x, z]) => {
        const column = new THREE.Mesh(new THREE.BoxGeometry(0.16, floorHeight, 0.16), columnMaterial);
        column.position.set(x, y + floorHeight / 2, z);
        column.castShadow = true;
        tower.add(column);
      });

      if (isComplete) {
        const front = new THREE.Mesh(new THREE.BoxGeometry(width - 0.5, 0.62, 0.04), glassMaterial);
        front.position.set(0, y + floorHeight / 2, depth / 2 - 0.02);
        tower.add(front);
        const back = front.clone();
        back.position.z = -depth / 2 + 0.02;
        tower.add(back);
        const left = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.62, depth - 0.5), glassMaterial);
        left.position.set(-width / 2 + 0.02, y + floorHeight / 2, 0);
        tower.add(left);
        const right = left.clone();
        right.position.x = width / 2 - 0.02;
        tower.add(right);

        if (floor % 2 === 0 || floor === 3) {
          const lit = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.4, 0.05), warmGlass);
          lit.position.set(-1.4, y + floorHeight / 2 + 0.05, depth / 2 + 0.01);
          tower.add(lit);
          const lit2 = lit.clone();
          lit2.position.x = 1.2;
          lit2.scale.x = 0.8;
          tower.add(lit2);
        }
      } else {
        const edge = new THREE.Mesh(new THREE.BoxGeometry(width, 0.06, 0.06), warmGlass);
        edge.position.set(0, y + floorHeight, depth / 2);
        tower.add(edge);
        const edgeSide = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, depth), warmGlass);
        edgeSide.position.set(-width / 2, y + floorHeight, 0);
        tower.add(edgeSide);
      }
    }

    const core = new THREE.Mesh(
      new THREE.BoxGeometry(1.5, completed * floorHeight, 1.2),
      new THREE.MeshStandardMaterial({ color: 0x273449, roughness: 0.9 }),
    );
    core.position.set(0, (completed * floorHeight) / 2, 0);
    core.castShadow = true;
    tower.add(core);

    const parapet = new THREE.Mesh(
      new THREE.BoxGeometry(width + 0.2, 0.18, depth + 0.2),
      slabMaterial,
    );
    parapet.position.y = completed * floorHeight + 0.14;
    tower.add(parapet);

    tower.position.set(0.6, 0, 0.4);
    this.scene.add(tower);
  }

  private buildCrane(): void {
    if (!this.scene) {
      return;
    }
    const crane = new THREE.Group();
    const steel = new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      roughness: 0.38,
      metalness: 0.6,
    });
    const darkSteel = new THREE.MeshStandardMaterial({
      color: 0xb45309,
      roughness: 0.5,
      metalness: 0.5,
    });
    const height = 14;

    const legOffsets: [number, number][] = [
      [-0.32, -0.32],
      [0.32, -0.32],
      [-0.32, 0.32],
      [0.32, 0.32],
    ];
    legOffsets.forEach(([x, z]) => {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, height, 6), steel);
      leg.position.set(x, height / 2, z);
      leg.castShadow = true;
      crane.add(leg);
    });

    for (let i = 0; i <= height; i += 1.1) {
      const braceX = new THREE.Mesh(new THREE.BoxGeometry(0.64, 0.035, 0.035), darkSteel);
      braceX.position.set(0, i, -0.32);
      crane.add(braceX);
      const braceZ = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.035, 0.64), darkSteel);
      braceZ.position.set(0.32, i, 0);
      crane.add(braceZ);
      const diagonal = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.03, 0.03), darkSteel);
      diagonal.position.set(0, i + 0.55, 0.32);
      diagonal.rotation.z = Math.PI / 4.4;
      crane.add(diagonal);
    }

    const cab = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.6, 0.8), darkSteel);
    cab.position.set(0, height * 0.72, 0.55);
    crane.add(cab);

    const jib = new THREE.Group();
    jib.position.y = height;
    const jibLength = 10;
    const jibBeam = new THREE.Mesh(new THREE.BoxGeometry(jibLength, 0.16, 0.22), steel);
    jibBeam.position.x = jibLength / 2 - 1;
    jib.add(jibBeam);
    for (let i = 0; i < jibLength; i += 1.2) {
      const truss = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.42, 0.04), darkSteel);
      truss.position.set(i - 0.8, -0.18, 0);
      jib.add(truss);
    }
    const counter = new THREE.Mesh(new THREE.BoxGeometry(3.2, 0.2, 0.24), steel);
    counter.position.x = -2.7;
    jib.add(counter);

    const head = new THREE.Mesh(new THREE.ConeGeometry(0.22, 1.4, 4), steel);
    head.position.set(0, 1.1, 0);
    jib.add(head);

    const cable = new THREE.Mesh(
      new THREE.CylinderGeometry(0.006, 0.006, 6.4, 4),
      new THREE.MeshStandardMaterial({ color: 0x94a3b8 }),
    );
    cable.position.set(jibLength - 2, -3.2, 0);
    jib.add(cable);

    const hookGroup = new THREE.Group();
    hookGroup.position.set(jibLength - 2, -6.4, 0);
    const block = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.24, 0.24), darkSteel);
    hookGroup.add(block);
    const hook = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.035, 8, 16), steel);
    hook.rotation.x = Math.PI / 2;
    hook.position.y = -0.22;
    hookGroup.add(hook);
    jib.add(hookGroup);
    this.hook = hookGroup;

    crane.add(jib);
    crane.position.set(-7.4, 0, -2.6);
    this.crane = crane;
    this.scene.add(crane);
  }

  private buildSite(): void {
    if (!this.scene) {
      return;
    }
    const containerMaterial = (color: number) =>
      new THREE.MeshStandardMaterial({ color, roughness: 0.72, metalness: 0.2 });

    const containers: [number, number, number, number][] = [
      [5.4, 0.6, 4.1, 0xf59e0b],
      [7.2, 0.6, 4.1, 0x1d4ed8],
      [5.4, 0.6, 6.1, 0x334155],
    ];
    containers.forEach(([x, y, z, color]) => {
      const box = new THREE.Mesh(new THREE.BoxGeometry(1.5, 1.2, 1.1), containerMaterial(color));
      box.position.set(x, y, z);
      box.castShadow = true;
      box.receiveShadow = true;
      this.scene!.add(box);
    });

    const materialBarrier = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.8 });
    const posts = new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.6 });
    for (let i = 0; i < 10; i += 1) {
      const panel = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.1, 0.05), materialBarrier);
      panel.position.set(-4.5 + i * 1.15, 0.55, 7.4);
      this.scene.add(panel);
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.07, 1.1, 0.07), posts);
      post.position.set(-4.5 + i * 1.15 - 0.55, 0.55, 7.4);
      this.scene.add(post);
    }

    const materialPile = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.95 });
    for (let i = 0; i < 5; i += 1) {
      const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 1.5, 10), materialPile);
      pipe.rotation.z = Math.PI / 2;
      pipe.position.set(-5.2, 0.15 + i * 0.13, 4.2);
      pipe.castShadow = true;
      this.scene.add(pipe);
    }

    const materialPallet = new THREE.MeshStandardMaterial({ color: 0x8b5e34, roughness: 0.9 });
    for (let i = 0; i < 3; i += 1) {
      const pallet = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.16, 0.9), materialPallet);
      pallet.position.set(3.4, 0.08 + i * 0.18, -4.6);
      pallet.castShadow = true;
      this.scene.add(pallet);
    }

    const materialTowerLight = new THREE.MeshStandardMaterial({
      color: 0x7f1d1d,
      emissive: 0xef4444,
      emissiveIntensity: 2,
    });
    const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 8), materialTowerLight);
    beacon.position.set(-7.4, 14.2, -2.6);
    this.scene.add(beacon);
  }

  private buildDust(): void {
    if (!this.scene) {
      return;
    }
    const count = 90;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 24;
      positions[i * 3 + 1] = Math.random() * 11;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 24;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    this.dust = new THREE.Points(
      geometry,
      new THREE.PointsMaterial({
        color: 0xfbbf24,
        size: 0.045,
        transparent: true,
        opacity: 0.5,
        depthWrite: false,
      }),
    );
    this.scene.add(this.dust);
  }

  private animate = (): void => {
    if (this.disposed) {
      return;
    }
    this.frame = requestAnimationFrame(this.animate);
    const delta = Math.min(this.clock.getDelta(), 0.05);
    const elapsed = this.clock.elapsedTime;

    if (!this.reducedMotion) {
      if (!this.pointerDown && performance.now() - this.lastInteraction > 2400) {
        this.autoRotate = true;
      }
      if (this.autoRotate) {
        this.theta += delta * 0.075;
      }
      if (this.crane) {
        this.crane.rotation.y += delta * 0.055;
      }
      if (this.hook) {
        this.hook.position.y = -6.4 + Math.sin(elapsed * 1.1) * 0.22;
      }
      if (this.dust) {
        this.dust.rotation.y -= delta * 0.012;
        this.dust.position.y = Math.sin(elapsed * 0.35) * 0.25;
      }
    }

    this.updateCamera();
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  };

  private onPointerDown = (event: PointerEvent): void => {
    if (event.button !== 0) {
      return;
    }
    this.pointerDown = true;
    this.autoRotate = false;
    this.lastX = event.clientX;
    this.lastY = event.clientY;
    this.lastInteraction = performance.now();
    (event.target as HTMLElement).setPointerCapture?.(event.pointerId);
  };

  private onPointerMove = (event: PointerEvent): void => {
    if (!this.pointerDown) {
      return;
    }
    const dx = event.clientX - this.lastX;
    const dy = event.clientY - this.lastY;
    this.lastX = event.clientX;
    this.lastY = event.clientY;
    this.theta -= dx * 0.007;
    this.phi = THREE.MathUtils.clamp(this.phi - dy * 0.005, 0.5, 1.36);
    this.lastInteraction = performance.now();
  };

  private onPointerUp = (): void => {
    this.pointerDown = false;
    this.lastInteraction = performance.now();
  };

  private onWheel = (event: WheelEvent): void => {
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }
    event.preventDefault();
    this.radius = THREE.MathUtils.clamp(this.radius + event.deltaY * 0.02, 10, 32);
    this.lastInteraction = performance.now();
  };

  private onVisibility = (): void => {
    if (document.hidden) {
      cancelAnimationFrame(this.frame);
    } else if (!this.disposed) {
      this.clock.getDelta();
      this.animate();
    }
  };
}
