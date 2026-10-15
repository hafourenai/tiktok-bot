import { render } from "preact";

import UploadPage from "./pages/Upload";
import TabbedPage from "./pages/Conversion/TabbedPage";
import { initTheme } from "./ThemeStore";
import Popup from "./components/Popup";
import FullPageDropOverlay from "./components/FullPageDropOverlay";
import { initMode } from "./ModeStore";
import { CurrentPage, Pages } from "./AppState";
import "./components/StyledButton/index.css";
export { CurrentPage, LoadingToolsText, Pages, PopupData } from "./AppState";

console.log("Rendering UI");

function App() {
  return (
    <>
      {CurrentPage.value === Pages.Conversion && <TabbedPage />}
      {CurrentPage.value === Pages.Upload && <UploadPage />}
      <FullPageDropOverlay />
      <Popup />
    </>
  );
}

render(<App />, document.getElementById("app")!);

initTheme();
initMode();
