#include <windows.h>
#include <windowsx.h>            // For GET_X_LPARAM/GET_Y_LPARAM
#include <shellscalingapi.h>   // For SetProcessDpiAwareness
#include <gdiplus.h>
#include <thread>
#include <string>
#include <iostream>
#include <atomic>
#include <sstream>
#include <algorithm>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "Shcore.lib")

using namespace Gdiplus;

enum HUDState { STATE_CLEAR = 0, STATE_OK = 1, STATE_FAIL = 2 };
std::atomic<int> hudState(STATE_CLEAR);
float hudScore = 0.0f;
int hudX = 800, hudY = 500;
const int hudHeight = 128;  // Fixed height
HWND hwnd;
bool dragging = false;
POINT dragOffset;

// Draw text with a subtle glow: only 4-directional and reduced alpha
void DrawGlowingText(Graphics& g, const std::wstring& text,
                     Font& font, PointF pos,
                     Color glowColor, Color textColor) {
    SolidBrush glowBrush(glowColor), textBrush(textColor);
    const int offsets[4][2] = {{-1,0},{1,0},{0,-1},{0,1}};
    for (auto& off : offsets) {
        g.DrawString(text.c_str(), -1, &font,
                     PointF(pos.X + off[0], pos.Y + off[1]), &glowBrush);
    }
    g.DrawString(text.c_str(), -1, &font, pos, &textBrush);
}

void ClearHUD() {
    Bitmap bmp(1, 1, PixelFormat32bppPARGB);
    Graphics g(&bmp);
    g.Clear(Color(0, 0, 0, 0));

    HDC screenDC = GetDC(NULL);
    HDC memDC = CreateCompatibleDC(screenDC);
    HBITMAP hBmp = nullptr;
    bmp.GetHBITMAP(Color(0,0,0,0), &hBmp);
    SelectObject(memDC, hBmp);

    SIZE size = {1, 1};
    POINT ptZero = {0, 0};
    BLENDFUNCTION blend = {AC_SRC_OVER, 0, 255, AC_SRC_ALPHA};
    UpdateLayeredWindow(hwnd, screenDC, NULL, &size,
                        memDC, &ptZero, 0, &blend, ULW_ALPHA);

    DeleteObject(hBmp);
    DeleteDC(memDC);
    ReleaseDC(NULL, screenDC);
}

void DrawHUD() {
    if (hudState == STATE_CLEAR) {
        ClearHUD();
        return;
    }

    int width = hudHeight * 3;
    int height = hudHeight;

    Bitmap bmp(width, height, PixelFormat32bppPARGB);
    Graphics g(&bmp);

    g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetCompositingMode(CompositingModeSourceCopy);
    g.Clear(Color(0,0,0,0));
    g.SetCompositingMode(CompositingModeSourceOver);

    GraphicsPath path;
    path.AddArc(0, 0, 20, 20, 180, 90);
    path.AddArc(width-20, 0, 20, 20, 270, 90);
    path.AddArc(width-20, height-20, 20, 20, 0, 90);
    path.AddArc(0, height-20, 20, 20, 90, 90);
    path.CloseFigure();
    SolidBrush bg(Color(180,20,20,20));
    g.FillPath(&bg, &path);

    FontFamily ff(L"Microsoft YaHei");
    Font font1(&ff, height*0.23f, FontStyleBold, UnitPixel);
    Font font2(&ff, height*0.30f, FontStyleBold, UnitPixel);

    std::wstring prefix = (hudState == STATE_OK)
        ? L"\u5efa\u8bae\uFF1A\u5f3a\u5316"
        : L"\u5efa\u8bae\uFF1A\u5f03\u7f6e";
    Color preGlow(100,255,255,255);
    DrawGlowingText(g, prefix, font1,
                    PointF(10, height*0.10f),
                    preGlow, Color(255,255,255,255));

    Pen pen(Color(80,255,255,255), 1.5f);
    g.DrawLine(&pen, (REAL)10, (REAL)(height*0.45f),
               (REAL)(width-10), (REAL)(height*0.45f));

    wchar_t buf[32];
    swprintf(buf, 32, L"%.3f%%", hudScore*100.0f);
    Color pctColor = (hudState == STATE_OK)
        ? Color(255,0,200,0)
        : Color(255,200,0,0);
    Color pctGlowColor(100, pctColor.GetR(), pctColor.GetG(), pctColor.GetB());
    DrawGlowingText(g, buf, font2,
                    PointF(10, height*0.55f),
                    pctGlowColor, pctColor);

    HDC screenDC = GetDC(NULL);
    HDC memDC = CreateCompatibleDC(screenDC);
    HBITMAP hBmp = nullptr;
    bmp.GetHBITMAP(Color(0,0,0,0), &hBmp);
    SelectObject(memDC, hBmp);

    SIZE size = {width, height};
    POINT ptSrc = {0, 0};
    POINT ptDst = { hudX, hudY };
    BLENDFUNCTION blend = {AC_SRC_OVER, 0, 255, AC_SRC_ALPHA};

    UpdateLayeredWindow(hwnd, screenDC, NULL,
                        &size, memDC, &ptSrc,
                        0, &blend, ULW_ALPHA);
    SetWindowPos(hwnd, HWND_TOPMOST,
                 ptDst.x, ptDst.y,
                 width, height,
                 SWP_NOACTIVATE);

    DeleteObject(hBmp);
    DeleteDC(memDC);
    ReleaseDC(NULL, screenDC);
}

LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_LBUTTONDOWN:
        dragging = true;
        {
            POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };
            dragOffset.x = pt.x;
            dragOffset.y = pt.y;
        }
        SetCapture(hWnd);
        return 0;

    case WM_MOUSEMOVE:
        if (dragging) {
            POINT ptScreen;
            GetCursorPos(&ptScreen);
            hudX = ptScreen.x - dragOffset.x;
            hudY = ptScreen.y - dragOffset.y;
            PostMessage(hwnd, WM_APP+1, 0, 0);
        }
        return 0;

    case WM_LBUTTONUP:
        dragging = false;
        ReleaseCapture();
        return 0;

    case WM_APP + 1:
        DrawHUD();
        return 0;
    }
    return DefWindowProc(hWnd, msg, wParam, lParam);
}

void InputThread() {
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream iss(line);
        std::string cmd;
        float score;
        if (!(iss >> cmd)) continue;
        if ((cmd == "ok" || cmd == "fail") && (iss >> score)) {
            hudScore = std::clamp(score, 0.0f, 1.0f);
            hudState = (cmd == "ok") ? STATE_OK : STATE_FAIL;
            PostMessage(hwnd, WM_APP+1, 0, 0);
        } else if (cmd == "clear") {
            hudState = STATE_CLEAR;
            PostMessage(hwnd, WM_APP+1, 0, 0);
        }
    }
}

int main() {
    SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE);

    GdiplusStartupInput gdiplusInput;
    ULONG_PTR gdiplusToken;
    GdiplusStartup(&gdiplusToken, &gdiplusInput, NULL);

    HINSTANCE hInst = GetModuleHandle(NULL);
    WNDCLASSW wc = {};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.lpszClassName = L"HUDWindow";
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    RegisterClassW(&wc);

    hwnd = CreateWindowExW(
        WS_EX_LAYERED | WS_EX_TOOLWINDOW,
        wc.lpszClassName, L"", WS_POPUP,
        0,0,1,1, NULL, NULL, hInst, NULL);
    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);

    std::thread(InputThread).detach();
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    GdiplusShutdown(gdiplusToken);
    return 0;
}