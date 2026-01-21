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
    public void testBuildScriptContainsGradle9Comment() throws IOException {
        // 1. Get build file path from system property
        String buildFilePath = System.getProperty("sample.buildFile");
        assertNotNull(buildFilePath, "System property 'sample.buildFile' must be set by the runner");

        // 2. Setup project directory - MINIMAL SETUP ONLY
        File projectDir = tempDir.toFile();
        Files.writeString(new File(projectDir, "settings.gradle.kts").toPath(), "rootProject.name = \"test-project\"\n");

        // 3. Copy build file to project directory
        Path buildFile = new File(projectDir, "build.gradle.kts").toPath();
        Files.copy(
                Path.of(buildFilePath),
                buildFile,
                StandardCopyOption.REPLACE_EXISTING
        );

        // 4. Read the build file content and verify it contains the Gradle 9.0.0 comment
        String buildFileContent = Files.readString(buildFile);
        
        // 5. Assert that the comment exists - this is what the fix added
        assertTrue(
                buildFileContent.contains("// Move to returning `properties[\"BACKEND_URL\"] as String?` after upgrading to Gradle 9.0.0"),
                "Build script should contain the comment about simplification after Gradle 9.0.0 upgrade. " +
                "This comment provides important context for future refactoring."
        );
        
        // 6. Also verify the backendUrl provider setup is present to ensure we're testing the right section
        assertTrue(
                buildFileContent.contains("val backendUrl = providers.fileContents("),
                "Build script should contain the backendUrl provider configuration"
        );
        
        assertTrue(
                buildFileContent.contains("if (properties.containsKey(\"BACKEND_URL\"))"),
                "Build script should contain the BACKEND_URL property check"
        );
        
        assertTrue(
                buildFileContent.contains(".orElse(\"http://example.com\")"),
                "Build script should contain the fallback URL configuration"
        );
    }

    @Test
    public void testBuildScriptSyntaxIsValid() throws IOException {
        // 1. Get build file path from system property
        String buildFilePath = System.getProperty("sample.buildFile");
        assertNotNull(buildFilePath, "System property 'sample.buildFile' must be set by the runner");

        // 2. Setup project directory - MINIMAL SETUP ONLY
        File projectDir = tempDir.toFile();
        Files.writeString(new File(projectDir, "settings.gradle.kts").toPath(), "rootProject.name = \"test-project\"\n");

        // 3. Copy build file to project directory
        Files.copy(
                Path.of(buildFilePath),
                new File(projectDir, "build.gradle.kts").toPath(),
                StandardCopyOption.REPLACE_EXISTING
        );

        // 4. Run Gradle help task to verify the build script syntax is valid
        // This ensures the comment addition didn't break anything
        BuildResult result = GradleRunner.create()
                .withProjectDir(projectDir)
                .withArguments("help", "--stacktrace")
                .buildAndFail(); // Will fail due to missing Android SDK, but syntax should be valid
        
        // 5. Verify that the failure is not due to syntax errors in the build script
        String output = result.getOutput();
        assertFalse(
                output.contains("Unexpected character") || output.contains("Expecting an element"),
                "Build script should not have syntax errors. The comment should be properly formatted."
        );
    }
}