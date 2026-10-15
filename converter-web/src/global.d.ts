import type { FileData, ConvertPathNode, HandlerDefinition } from "./FormatHandler.js";
import type { TraversionGraph } from "./TraversionGraph.js";
import type { Remote } from "comlink";

declare global {
  interface Window {
    handlerDefs: HandlerDefinition[];
    traversionGraph: Remote<TraversionGraph>;
    printSupportedFormatCache: () => string;
    showPopup: (html: string) => void;
    hidePopup: () => void;
    tryConvertByTraversing: (
      files: FileData[],
      from: ConvertPathNode,
      to: ConvertPathNode,
      signal?: AbortSignal,
    ) => Promise<{
      files: FileData[];
      path: ConvertPathNode[];
    } | null>;
  }

  var baseUrl: string | undefined;
}
