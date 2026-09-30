import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

import { expandScene, expandableNodeIds } from "./src/expansion";
import { expandedDetailSize, fullyExpandedDetailTree } from "./src/detail-layout";
import { DETAIL_KIND_NAMES } from "./src/module-details";
import { DEFAULT_OPTIONS, optionCombinations, SCENARIOS } from "./src/scenarios";
import { renderCaseIndex, renderGalleryIndex, renderSceneSvg } from "./src/svg-export";

function caseMatrixPlugin(): Plugin {
  return {
    name: "archcanvas-scene-lab-case-matrix",
    generateBundle() {
      const manifest: Array<Record<string, unknown>> = [];
      for (const scene of SCENARIOS) {
        const expansionVariants: Array<{ name: string; label: string; metrics: ReturnType<typeof renderSceneSvg>["metrics"] }> = [];
        const expandableIds = expandableNodeIds(scene);
        if (expandableIds.length) {
          const detailKindCounts = new Map<string, number>();
          for (const node of scene.nodes.filter((item) => item.detail_kind)) {
            detailKindCounts.set(node.detail_kind!, (detailKindCounts.get(node.detail_kind!) ?? 0) + 1);
          }
          for (const node of scene.nodes.filter((item) => item.detail_kind)) {
            const snapshot = {
              name: detailKindCounts.get(node.detail_kind!) === 1
                ? `expanded-${node.detail_kind}`
                : `expanded-${node.scene_node_id}`,
              label: detailKindCounts.get(node.detail_kind!) === 1
                ? `仅展开${DETAIL_KIND_NAMES[node.detail_kind!]}`
                : `仅展开${node.label} · ${DETAIL_KIND_NAMES[node.detail_kind!]}`,
            };
            const expandedScene = expandScene(scene, new Set([node.scene_node_id]));
            const { svg, metrics } = renderSceneSvg(expandedScene, DEFAULT_OPTIONS);
            expansionVariants.push({ name: snapshot.name, label: snapshot.label, metrics });
            this.emitFile({ type: "asset", fileName: `cases/${scene.scene_id}/${snapshot.name}.svg`, source: svg });
            this.emitFile({
              type: "asset",
              fileName: `cases/${scene.scene_id}/${snapshot.name}.json`,
              source: JSON.stringify({ scene: expandedScene, expandedNodeIds: [node.scene_node_id], options: DEFAULT_OPTIONS, metrics }, null, 2),
            });
          }
          const detailExpansions = Object.fromEntries(scene.nodes.flatMap((node) => (
            expandableIds.includes(node.scene_node_id) && node.detail_kind
              ? [[node.scene_node_id, fullyExpandedDetailTree(node.detail_kind)]]
              : []
          )));
          const expandedSizes = Object.fromEntries(scene.nodes.flatMap((node) => (
            node.detail_kind && detailExpansions[node.scene_node_id]
              ? [[node.scene_node_id, expandedDetailSize(node.detail_kind, detailExpansions[node.scene_node_id])]]
              : []
          )));
          const expandedScene = expandScene(scene, new Set(expandableIds), expandedSizes);
          const { svg, metrics } = renderSceneSvg(expandedScene, DEFAULT_OPTIONS, {}, detailExpansions);
          expansionVariants.push({ name: "expanded-all", label: "全部展开到原子级", metrics });
          this.emitFile({ type: "asset", fileName: `cases/${scene.scene_id}/expanded-all.svg`, source: svg });
          this.emitFile({
            type: "asset",
            fileName: `cases/${scene.scene_id}/expanded-all.json`,
            source: JSON.stringify({ scene: expandedScene, expandedNodeIds: expandableIds, detailExpansions, options: DEFAULT_OPTIONS, metrics }, null, 2),
          });
        }
        const variants = optionCombinations().map((options) => {
          const name = `${options.routeStyle}-${options.nodeStyle}-${options.labelStyle}`;
          const { svg, metrics } = renderSceneSvg(scene, options);
          const record = { name, sceneId: scene.scene_id, options, metrics };
          manifest.push(record);
          this.emitFile({ type: "asset", fileName: `cases/${scene.scene_id}/${name}.svg`, source: svg });
          this.emitFile({
            type: "asset",
            fileName: `cases/${scene.scene_id}/${name}.json`,
            source: JSON.stringify({ scene, options, metrics }, null, 2),
          });
          return { name, options, metrics };
        });
        this.emitFile({
          type: "asset",
          fileName: `cases/${scene.scene_id}/index.html`,
          source: renderCaseIndex(scene, variants, expansionVariants),
        });
      }
      this.emitFile({ type: "asset", fileName: "cases/index.html", source: renderGalleryIndex(SCENARIOS) });
      this.emitFile({ type: "asset", fileName: "cases/manifest.json", source: JSON.stringify(manifest, null, 2) });
    },
  };
}

export default defineConfig({
  root: decodeURIComponent(new URL(".", import.meta.url).pathname),
  base: "./",
  plugins: [react(), caseMatrixPlugin()],
  build: {
    outDir: "../../../build/scene-visual-lab",
    emptyOutDir: true,
    assetsDir: "assets",
  },
});
