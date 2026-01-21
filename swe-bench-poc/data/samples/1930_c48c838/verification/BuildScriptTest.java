import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

import static org.junit.jupiter.api.Assertions.*;

public class BuildScriptTest {

    @TempDir
    Path tempDir;

    @Test
    public void testTestOptionsConfiguration() throws IOException {
        // 1. Get build file path from system property
        String buildFilePath = System.getProperty("sample.buildFile");
        assertNotNull(buildFilePath, "System property 'sample.buildFile' must be set by the runner");

        // 2. Setup project directory - MINIMAL SETUP ONLY
        File projectDir = tempDir.toFile();
        Files.writeString(new File(projectDir, "settings.gradle.kts").toPath(), 
            "rootProject.name = \"test-project\"\n");

        // 3. Copy build file to project directory
        Files.copy(
                Path.of(buildFilePath),
                new File(projectDir, "build.gradle.kts").toPath(),
                StandardCopyOption.REPLACE_EXISTING
        );

        // 4. Read the build file content to verify the structure
        String buildFileContent = Files.readString(new File(projectDir, "build.gradle.kts").toPath());

        // 5. Assert on the build file structure
        // The MODIFIED version should use the single-line syntax: testOptions.unitTests.isIncludeAndroidResources = true
        // The ORIGINAL version used a block syntax with testOptions { unitTests { isIncludeAndroidResources = true } }
        
        // Check that the build file uses the correct single-line syntax
        assertTrue(
                buildFileContent.contains("testOptions.unitTests.isIncludeAndroidResources = true"),
                "Build file should use single-line syntax 'testOptions.unitTests.isIncludeAndroidResources = true'"
        );

        // Check that the build file does NOT use the block syntax
        assertFalse(
                buildFileContent.matches("(?s).*testOptions\\s*\\{\\s*unitTests\\s*\\{\\s*isIncludeAndroidResources\\s*=\\s*true\\s*\\}\\s*\\}.*"),
                "Build file should NOT use block syntax for testOptions configuration"
        );

        // 6. Verify that the build file can be evaluated without syntax errors
        // Using help task as a simple way to verify the build file is syntactically correct
        BuildResult result = GradleRunner.create()
                .withProjectDir(projectDir)
                .withArguments("help", "--stacktrace")
                .build();

        // Verify the build succeeded
        assertNotNull(result, "Build result should not be null");
        assertTrue(
                result.getOutput().contains("BUILD SUCCESSFUL") || result.getOutput().contains("help"),
                "Build should complete successfully with the corrected testOptions syntax"
        );
    }
}