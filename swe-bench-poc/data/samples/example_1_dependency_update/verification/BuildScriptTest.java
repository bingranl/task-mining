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
    public void testJUnit5DependencyPresent() throws IOException {
        String buildFilePath = System.getProperty("sample.buildFile");
        assertNotNull(buildFilePath, "System property 'sample.buildFile' must be set by the runner");

        File projectDir = tempDir.toFile();
        Files.writeString(new File(projectDir, "settings.gradle.kts").toPath(), "rootProject.name = \"test-project\"\n");

        Files.copy(
                Path.of(buildFilePath),
                new File(projectDir, "build.gradle.kts").toPath(),
                StandardCopyOption.REPLACE_EXISTING
        );

        BuildResult result = GradleRunner.create()
                .withProjectDir(projectDir)
                .withArguments("dependencies", "--configuration", "testRuntimeClasspath", "--stacktrace")
                .build();

        assertTrue(
                result.getOutput().contains("org.junit.jupiter:junit-jupiter:5.10.0"),
                "Expected JUnit 5 dependency 'org.junit.jupiter:junit-jupiter:5.10.0' to be present"
        );
    }
}
