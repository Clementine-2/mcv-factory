"""Auto-generated mobile-app / game / userscript scaffolders (E3).

Registered in generation/__init__.py:first_party_scaffolds per MODELS keys.
每个蓝图都生成一个最小但完整可运行的示例，并附带针对示例的测试。

注意：MODELS 的键必须是生成时传入的 scaffold recipe id（mobile-flutter、
mobile-kotlin、mobile-swift、game-bevy、game-godot、userscript-ts），它们与
generation/__init__.py 中注册的 handler 键一致；验证套件使用独立的
verification_recipe（如 flutter-mobile、bevy-game）。
"""
from __future__ import annotations

import re
from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command

MODELS = {
    "mobile-flutter": dict(files={
        'pubspec.yaml': '''name: __PKG__
description: __PURPOSE__
version: 0.1.0
environment:
  sdk: ">=3.0.0 <4.0.0"
dependencies:
  flutter:
    sdk: flutter
dev_dependencies:
  flutter_test:
    sdk: flutter
''',
        'lib/main.dart': '''// PURPOSE: __PURPOSE__
import 'package:flutter/material.dart';

/// 示例功能：拼接问候语，可被 widget 测试直接断言。
String buildGreeting(String name) => 'Hello, $name!';

/// 最小可运行示例 Widget：展示一条问候语。
class GreetingApp extends StatelessWidget {
  const GreetingApp({super.key, this.name = 'world'});

  final String name;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Center(
          child: Text(buildGreeting(name)),
        ),
      ),
    );
  }
}

void main() {
  runApp(const GreetingApp());
}
''',
        'test/widget_test.dart': '''// 针对示例 Widget 与逻辑编写 flutter test，直接断言行为。
import 'package:flutter_test/flutter_test.dart';
import 'package:__PKG__/main.dart';

void main() {
  testWidgets('renders greeting text', (WidgetTester tester) async {
    await tester.pumpWidget(const GreetingApp());
    expect(find.text('Hello, world!'), findsOneWidget);
  });

  test('buildGreeting joins name', () {
    expect(buildGreeting('world'), 'Hello, world!');
  });

  test('buildGreeting empty name', () {
    expect(buildGreeting(''), 'Hello, !');
  });
}
''',
    },
                 init=None,
                 build=['flutter', 'analyze'],
                 test=['flutter', 'test'],
                 artifacts=['pubspec.lock'],
                 family='mobile-app', work='mobile-app', tech='flutter',
                 provider='flutter', recipe='mobile-flutter', rt='dart'),
    "mobile-kotlin": dict(files={
        'build.gradle.kts': '''plugins {
    id("com.android.application") version "8.2.2" apply false
    kotlin("android") version "1.9.24" apply false
}
''',
        'settings.gradle.kts': '''pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "__PKG__"
include(":app")
''',
        'src/main/kotlin/App.kt': '''// PURPOSE: __PURPOSE__
package app

// buildGreeting 拼接问候语，作为示例功能供测试断言。
fun buildGreeting(name: String): String = "Hello, $name!"

// add 返回两个整数的和，作为示例功能供测试断言。
fun add(left: Int, right: Int): Int = left + right
''',
        'app/build.gradle.kts': '''plugins {
    id("com.android.application")
    kotlin("android")
}

android {
    namespace = "app"
    compileSdk = 34

    defaultConfig {
        applicationId = "app"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.6.1")
    testImplementation("junit:junit:4.13.2")
}
''',
        'app/src/main/AndroidManifest.xml': '''<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:label="__PKG__"
        android:theme="@style/Theme.AppCompat.Light.DarkActionBar">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
''',
        'app/src/main/kotlin/app/MainActivity.kt': '''// PURPOSE: __PURPOSE__
package app

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val text = TextView(this)
        text.text = buildGreeting("world")
        setContentView(text)
    }
}
''',
        'app/src/test/kotlin/app/AppLogicTest.kt': '''// 针对示例功能编写单元测试，直接断言行为。
package app

import org.junit.Assert.assertEquals
import org.junit.Test

class AppLogicTest {

    @Test
    fun greetingJoinsName() {
        assertEquals("Hello, world!", buildGreeting("world"))
    }

    @Test
    fun greetingEmptyName() {
        assertEquals("Hello, !", buildGreeting(""))
    }

    @Test
    fun addPositive() {
        assertEquals(5, add(2, 3))
    }

    @Test
    fun addNegative() {
        assertEquals(0, add(-1, 1))
    }
}
''',
    },
                 init=None,
                 build=['gradle', 'assembleDebug', '--offline'],
                 test=['gradle', 'test', '--offline'],
                 artifacts=['build/outputs/*'],
                 family='mobile-app', work='mobile-app', tech='kotlin',
                 provider='kotlin', recipe='mobile-kotlin', rt='kotlin'),
    "mobile-swift": dict(files={
        'Package.swift': '''// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "__PKG__",
    targets: [
        .target(name: "__MOD__Core", path: "Sources/__MOD__Core"),
        .executableTarget(name: "__MOD__", dependencies: ["__MOD__Core"], path: "Sources/__MOD__"),
        .testTarget(name: "__MOD__Tests", dependencies: ["__MOD__Core"], path: "Tests/__MOD__Tests"),
    ]
)
''',
        'Sources/__MOD__Core/Core.swift': '''// PURPOSE: __PURPOSE__

/// 示例功能：拼接问候语，可被可执行入口与 XCTest 共用。
public func buildGreeting(_ name: String) -> String {
    return "Hello, \\(name)!"
}

/// 示例功能：返回两个整数的和。
public func add(_ left: Int, _ right: Int) -> Int {
    return left + right
}
''',
        'Sources/__MOD__/main.swift': '''// PURPOSE: __PURPOSE__
import __MOD__Core

// 最小可运行示例：根据命令行参数输出问候或加法结果。
let args = CommandLine.arguments
if args.count == 3, args[1] == "greet" {
    print(buildGreeting(args[2]))
} else if args.count == 4, args[1] == "add", let left = Int(args[2]), let right = Int(args[3]) {
    print(add(left, right))
} else {
    print("Project scaffold ready. Implement domain behavior through the coding-agent workflow.")
}
''',
        'Tests/__MOD__Tests/CoreTests.swift': '''// 针对示例功能编写 XCTest，直接断言行为。
import XCTest
@testable import __MOD__Core

final class __MOD__CoreTests: XCTestCase {
    func testBuildGreetingJoinsName() {
        XCTAssertEqual(buildGreeting("world"), "Hello, world!")
    }

    func testBuildGreetingEmptyName() {
        XCTAssertEqual(buildGreeting(""), "Hello, !")
    }

    func testAddPositive() {
        XCTAssertEqual(add(2, 3), 5)
    }

    func testAddNegative() {
        XCTAssertEqual(add(-1, 1), 0)
    }
}
''',
    },
                 init=None,
                 build=['swift', 'build'],
                 test=['swift', 'test'],
                 artifacts=['.build/debug/*'],
                 family='mobile-app', work='mobile-app', tech='swift',
                 provider='swift', recipe='mobile-swift', rt='swift'),
    "game-bevy": dict(files={
        'Cargo.toml': '''[package]
name = "__PKG__"
version = "0.1.0"
edition = "2021"

[dependencies]
bevy = "0.13"
''',
        'src/main.rs': '''// PURPOSE: __PURPOSE__
use bevy::prelude::*;

/// 示例逻辑：速度倍率，可被单元测试直接断言。
pub fn speed_factor(base: f32) -> f32 {
    (base * 2.0).max(0.0)
}

/// 最小 App 逻辑：每帧把实体沿 X 轴平移，证明系统可注册并运行。
pub fn move_right(mut query: Query<&mut Transform>) {
    for mut transform in &mut query {
        transform.translation.x += 1.0;
    }
}

fn main() {
    App::new()
        .add_plugins(DefaultPlugins)
        .add_systems(Update, move_right)
        .run();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn speed_factor_scales_base() {
        assert_eq!(speed_factor(2.0), 4.0);
    }

    #[test]
    fn speed_factor_never_negative() {
        assert!(speed_factor(-5.0) >= 0.0);
    }

    #[test]
    fn add_system_can_be_spawned_without_renderer() {
        // 用无插件的最小 App 注册系统，验证示例逻辑可独立驱动。
        let mut app = App::new();
        app.add_systems(Update, move_right);
        app.update();
    }
}
''',
    },
                 init=None,
                 build=['cargo', 'build', '--offline'],
                 test=['cargo', 'test', '--offline'],
                 artifacts=['target/debug/*'],
                 family='game', work='game', tech='rust,bevy',
                 provider='cargo', recipe='game-bevy', rt='rust'),
    "game-godot": dict(files={
        'project.godot': '''; Engine configuration for __PKG__
; PURPOSE: __PURPOSE__
[application]

config/name="__PKG__"
''',
        'scripts/game_logic.gd': '''# PURPOSE: __PURPOSE__
# 示例游戏逻辑：可被 main 场景与测试脚本复用（通过 preload 引用）。

static func score_for(hits: int) -> int:
	return hits * 10

static func speed_factor(base: float) -> float:
	return maxf(base * 2.0, 0.0)
''',
        'main.gd': '''# PURPOSE: __PURPOSE__
extends Node

const GameLogic = preload("res://scripts/game_logic.gd")

func _ready() -> void:
	print("Project scaffold ready. Example score: ", GameLogic.score_for(3))
''',
        'tests/test_main.gd': '''# 针对示例功能编写 GDScript 断言测试。
# 运行方式：godot --headless -s tests/test_main.gd（任一断言失败即退出非零状态）。
extends SceneTree

const GameLogic = preload("res://scripts/game_logic.gd")

func _init() -> void:
	var failures: int = 0

	if GameLogic.score_for(3) != 30:
		print("FAIL: score_for(3)")
		failures += 1
	if GameLogic.score_for(0) != 0:
		print("FAIL: score_for(0)")
		failures += 1
	if GameLogic.speed_factor(2.0) != 4.0:
		print("FAIL: speed_factor(2.0)")
		failures += 1
	if GameLogic.speed_factor(-5.0) < 0.0:
		print("FAIL: speed_factor negative")
		failures += 1

	if failures == 0:
		print("ALL TESTS PASSED")
		quit(0)
	quit(1)
''',
    },
                 init=None,
                 build=['godot', '--headless', '--quit'],
                 test=['godot', '--headless', '-s', 'tests/test_main.gd'],
                 artifacts=['.godot/*'],
                 family='game', work='game', tech='godot',
                 provider='godot', recipe='game-godot', rt='gdscript'),
    "userscript-ts": dict(files={
        'package.json': '''{
  "name": "__PKG__",
  "version": "0.1.0",
  "description": "__PURPOSE__",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "tsc",
    "test": "node --test tests/userscript.test.mjs"
  },
  "devDependencies": {
    "typescript": "^5.5.0"
  }
}
''',
        'tsconfig.json': '''{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM"],
    "strict": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true
  },
  "include": ["src"]
}
''',
        'src/userscript.ts': '''// PURPOSE: __PURPOSE__
// ==UserScript==
// @name         __PKG__
// @namespace    project-factory
// @version      0.1.0
// @description  __PURPOSE__
// @match        https://example.com/*
// @grant        none
// ==/UserScript==

/// 示例纯逻辑：拼接问候语，可被测试直接断言。
export function buildGreeting(name: string): string {
  return `Hello, ${name}!`;
}

/// 示例纯逻辑：返回两个整数的和。
export function add(left: number, right: number): number {
  return left + right;
}

// 用户脚本入口：仅在浏览器环境（存在 document）时执行示例逻辑。
function main(): void {
  console.log(buildGreeting("world"));
}

if (typeof document !== "undefined") {
  main();
}
''',
        'tests/userscript.test.mjs': '''// 针对示例纯逻辑编写 Node 测试（需先 npm run build 生成 dist）。
import test from "node:test";
import assert from "node:assert/strict";
import { add, buildGreeting } from "../dist/userscript.js";

test("buildGreeting joins name", () => {
  assert.equal(buildGreeting("world"), "Hello, world!");
});

test("buildGreeting empty name", () => {
  assert.equal(buildGreeting(""), "Hello, !");
});

test("add positive numbers", () => {
  assert.equal(add(2, 3), 5);
});

test("add negative numbers", () => {
  assert.equal(add(-1, 1), 0);
});
''',
    },
                 init=None,
                 build=['npm', 'run', 'build'],
                 test=['npm', 'test'],
                 artifacts=['dist/*'],
                 family='userscript', work='userscript', tech='typescript',
                 provider='npm', recipe='userscript-ts', rt='node'),
}


def _fill_content(content: str, pkg: str, purpose: str, mod: str) -> str:
    return (
        content.replace("__PKG__", pkg)
        .replace("__MOD__", mod)
        .replace("__PURPOSE__", purpose)
    )


def _write_harness_context(project_root: Path, pkg: str, purpose: str) -> None:
    # E4: emit the canonical harness context file so Codex/Claude/Gemini skill
    # adapters can consume the generated project without extra setup.
    (project_root / "AGENTS.md").write_text(
        "# " + pkg + "\n\n" + purpose + "\n\nGenerated by Project Factory. "
        "Canonical harness adapters (codex/claude/gemini) read AGENTS.md.\n",
        encoding="utf-8",
    )


def _swift_module(project_name: str) -> str:
    # Swift 模块名必须是合法标识符，统一转为首字母大写的驼峰形式。
    value = re.sub(r"[^a-zA-Z0-9]", "", project_name) or "Demo"
    return value[0].upper() + value[1:]


def _scaffold_model(recipe: str, provider: ProviderView, project_name: str, project_root: Path,
                    staging_root: Path, purpose: str) -> ScaffoldResult:
    spec = MODELS.get(recipe)
    if spec is None:
        raise RecipeError(f"Unsupported E3 scaffold recipe: {recipe}")
    pkg = re.sub(r"[^a-z0-9_]+", "_", project_name.lower()).strip("_") or "demo"
    mod = _swift_module(project_name)
    project_root.mkdir(parents=True, exist_ok=False)
    # 先落地全部源文件/测试，再执行工具链初始化命令（若提供）。路径中的占位符同样替换。
    for rel, content in spec["files"].items():
        rel_filled = rel.replace("__PKG__", pkg).replace("__MOD__", mod)
        p = project_root / rel_filled
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_fill_content(content, pkg, purpose, mod), encoding="utf-8")
    if spec["init"] is not None:
        filled = [pkg if a == "__PKG__" else a for a in spec["init"]]
        run_command([provider.executable, *filled], project_root, timeout=600)
    _write_harness_context(project_root, pkg, purpose)
    return ScaffoldResult(
        command_result={"recipe": recipe, "provider": provider.executable},
        layout={"source": "src/" if spec["files"] else ".", "packaging": "manifest"},
    )


def scaffold_mobile_flutter(recipe, provider, project_name, project_root, staging_root, purpose):
    return _scaffold_model(recipe, provider, project_name, project_root, staging_root, purpose)


def scaffold_mobile_kotlin(recipe, provider, project_name, project_root, staging_root, purpose):
    return _scaffold_model(recipe, provider, project_name, project_root, staging_root, purpose)


def scaffold_mobile_swift(recipe, provider, project_name, project_root, staging_root, purpose):
    return _scaffold_model(recipe, provider, project_name, project_root, staging_root, purpose)


def scaffold_game_bevy(recipe, provider, project_name, project_root, staging_root, purpose):
    return _scaffold_model(recipe, provider, project_name, project_root, staging_root, purpose)


def scaffold_game_godot(recipe, provider, project_name, project_root, staging_root, purpose):
    return _scaffold_model(recipe, provider, project_name, project_root, staging_root, purpose)


def scaffold_userscript_ts(recipe, provider, project_name, project_root, staging_root, purpose):
    return _scaffold_model(recipe, provider, project_name, project_root, staging_root, purpose)
