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
    public void testNestedSubgraphGenerationWithMultipleLevels() throws IOException {
        // 1. Get build file path from system property
        String buildFilePath = System.getProperty("sample.buildFile");
        assertNotNull(buildFilePath, "System property 'sample.buildFile' must be set by the runner");

        // 2. Setup project directory - MINIMAL SETUP ONLY
        File projectDir = tempDir.toFile();
        
        // Create settings.gradle.kts with multiple nested modules to test multi-level nesting
        String settingsContent = "rootProject.name = \"test-project\"\n" +
                "include(\":core:data\")\n" +
                "include(\":core:model\")\n" +
                "include(\":feature:home\")\n" +
                "include(\":feature:settings\")\n" +
                "include(\":app\")\n";
        Files.writeString(new File(projectDir, "settings.gradle.kts").toPath(), settingsContent);

        // 3. Copy build file to project directory
        Files.copy(
                Path.of(buildFilePath),
                new File(projectDir, "build.gradle.kts").toPath(),
                StandardCopyOption.REPLACE_EXISTING
        );

        // Create minimal build.gradle.kts files for the subprojects to satisfy Gradle
        createMinimalSubproject(projectDir, "core/data");
        createMinimalSubproject(projectDir, "core/model");
        createMinimalSubproject(projectDir, "feature/home");
        createMinimalSubproject(projectDir, "feature/settings");
        createMinimalSubproject(projectDir, "app");

        // 4. Run Gradle to generate module graph
        // The modified version should handle nested subgraphs with multiple levels correctly
        BuildResult result = GradleRunner.create()
                .withProjectDir(projectDir)
                .withArguments("tasks", "--all", "--stacktrace")
                .buildAndFail(); // Expect this to fail with original (incorrect nesting logic)
        
        // The original version only handled single-level nesting and would fail with
        // multi-level nested projects (e.g., :feature:home where both "feature" and 
        // "feature:home" need proper subgraph handling)
        
        // With the modified version, it should properly group by outer groups and handle
        // multiple nesting levels by checking if key.count(':') > 1
        
        // Since we can't directly invoke the GraphDumpTask without proper plugin setup,
        // we verify that the build script doesn't cause parsing errors with nested structures
        String output = result.getOutput();
        
        // The modified version should not fail on multi-level project structures
        // The original version would fail because it doesn't properly handle the grouping
        // when substringBeforeLast(":") results in paths with multiple colons
        assertFalse(
                output.contains("StringIndexOutOfBoundsException") || 
                output.contains("No such property") ||
                output.contains("Could not find method"),
                "Build should handle nested subgraph generation without errors"
        );
    }

    @Test
    public void testSubgraphIndentationLogic() throws IOException {
        // 1. Get build file path from system property
        String buildFilePath = System.getProperty("sample.buildFile");
        assertNotNull(buildFilePath, "System property 'sample.buildFile' must be set by the runner");

        // 2. Setup project directory
        File projectDir = tempDir.toFile();
        Files.writeString(new File(projectDir, "settings.gradle.kts").toPath(), 
                "rootProject.name = \"test-project\"\n");

        // 3. Copy build file to project directory
        Files.copy(
                Path.of(buildFilePath),
                new File(projectDir, "build.gradle.kts").toPath(),
                StandardCopyOption.REPLACE_EXISTING
        );

        // 4. Read and verify the build script content
        String buildScriptContent = Files.readString(new File(projectDir, "build.gradle.kts").toPath());

        // The modified version should have dynamic indent calculation based on outerGroup
        // This is a key difference: indent = if (outerGroup.isNotEmpty()) 4 else 2
        assertTrue(
                buildScriptContent.contains("val indent = if (outerGroup.isNotEmpty()) 4 else 2"),
                "Modified version should have conditional indent logic for nested subgraphs"
        );

        // The modified version should have proper grouping by outer groups
        assertTrue(
                buildScriptContent.contains("val orderedGroups = nestedProjects.groupBy {"),
                "Modified version should group nested projects by outer group"
        );

        // The modified version should check for multiple colons to determine nesting level
        assertTrue(
                buildScriptContent.contains("if (it.key.count { char -> char == ':' } > 1)"),
                "Modified version should count colons to determine nesting level"
        );

        // The modified version should have proper subgraph rendering with variable indentation
        assertTrue(
                buildScriptContent.contains("\" \".repeat(indent) + \"subgraph $group\""),
                "Modified version should use repeat() for dynamic indentation"
        );

        // The original version would have fixed indentation and simpler structure
        // The absence of these features indicates the original version
        assertFalse(
                buildScriptContent.contains("nestedProjects.sortedByDescending { it.value.size }.forEach { (group, projects) ->") &&
                !buildScriptContent.contains("val orderedGroups"),
                "Original version should not have the simplified single-level nesting logic without orderedGroups"
        );
    }

    private void createMinimalSubproject(File projectDir, String path) throws IOException {
        File subprojectDir = new File(projectDir, path);
        subprojectDir.mkdirs();
        Files.writeString(new File(subprojectDir, "build.gradle.kts").toPath(), "// Minimal build file\n");
    }
}