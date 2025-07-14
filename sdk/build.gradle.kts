// SPDX-License-Identifier: Apache-2.0

plugins {
    id("base")
}

description = "Hiero Mirror Node Python SDK"

// Python SDK build tasks
tasks.register<Exec>("installDependencies") {
    description = "Install Python dependencies"
    group = "python"
    
    workingDir = projectDir
    commandLine = listOf("pip", "install", "-e", ".[dev]")
}

tasks.register<Exec>("format") {
    description = "Format Python code"
    group = "python"
    
    dependsOn("installDependencies")
    workingDir = projectDir
    commandLine = listOf("black", "hiero_mirror/", "examples/", "tests/")
}

tasks.register<Exec>("lint") {
    description = "Lint Python code"
    group = "python"
    
    dependsOn("installDependencies")
    workingDir = projectDir
    commandLine = listOf("flake8", "hiero_mirror/")
}

tasks.register<Exec>("typeCheck") {
    description = "Type check Python code"
    group = "python"
    
    dependsOn("installDependencies")
    workingDir = projectDir
    commandLine = listOf("mypy", "hiero_mirror/")
}

tasks.register<Exec>("test") {
    description = "Run Python tests"
    group = "python"
    
    dependsOn("installDependencies")
    workingDir = projectDir
    commandLine = listOf("pytest", "tests/", "-v", "--cov=hiero_mirror")
}

tasks.register<Exec>("buildPackage") {
    description = "Build Python package"
    group = "python"
    
    dependsOn("format", "lint", "typeCheck", "test")
    workingDir = projectDir
    commandLine = listOf("python", "-m", "build")
}

tasks.register<Exec>("publishPackage") {
    description = "Publish Python package"
    group = "python"
    
    dependsOn("buildPackage")
    workingDir = projectDir
    commandLine = listOf("twine", "upload", "dist/*")
}

tasks.register<Exec>("runExamples") {
    description = "Run Python examples"
    group = "python"
    
    dependsOn("installDependencies")
    workingDir = projectDir
    commandLine = listOf("python", "examples/basic_usage.py")
}

tasks.register<Exec>("clean") {
    description = "Clean Python build artifacts"
    group = "python"
    
    workingDir = projectDir
    commandLine = listOf("rm", "-rf", "build/", "dist/", "*.egg-info/", ".pytest_cache/", ".coverage", "htmlcov/")
}

// Add to main build
tasks.named("build") {
    dependsOn("buildPackage")
}

tasks.named("clean") {
    dependsOn("clean")
}