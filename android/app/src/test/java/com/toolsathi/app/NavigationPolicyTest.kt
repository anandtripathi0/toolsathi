package com.toolsathi.app

import org.junit.Assert.*
import org.junit.Test

class NavigationPolicyTest {
    private val policy = NavigationPolicy("https://toolsathi.test/")

    @Test fun trustsOnlyExactHttpsOrigin() {
        assertTrue(policy.isTrusted("https://toolsathi.test/tools/json-formatter/"))
        assertTrue(policy.isTrusted("https://TOOLSATHI.test:443/"))
        assertFalse(policy.isTrusted("http://toolsathi.test/"))
        assertFalse(policy.isTrusted("https://toolsathi.test:8443/"))
        assertFalse(policy.isTrusted("https://toolsathi.test.attacker.test/"))
        assertFalse(policy.isTrusted("https://toolsathi.test@attacker.test/"))
        assertFalse(policy.isTrusted("https://attacker:password@toolsathi.test/"))
        assertFalse(policy.isTrusted("file:///etc/passwd"))
        assertFalse(policy.isTrusted("content://provider/file"))
        assertFalse(policy.isTrusted("javascript:alert(1)"))
        assertFalse(policy.isTrusted(null))
    }

    @Test fun opensOnlyCredentialFreeHttpsExternally() {
        assertTrue(policy.isExternalHttps("https://docs.python.org/3/"))
        assertFalse(policy.isExternalHttps("intent://evil"))
        assertFalse(policy.isExternalHttps("https://secret@other.test/"))
        assertFalse(policy.isExternalHttps("https://toolsathi.test/"))
    }

    @Test fun stripsFilenameTraversalAndControls() {
        assertEquals("report.pdf", NavigationPolicy.safeFilename("../../report.pdf"))
        assertEquals("report.pdf", NavigationPolicy.safeFilename("C:\\secrets\\report.pdf"))
        assertEquals("toolsathi-result.txt", NavigationPolicy.safeFilename(".."))
        assertFalse(NavigationPolicy.safeFilename("bad\nname.pdf").contains('\n'))
        assertEquals(120, NavigationPolicy.safeFilename("a".repeat(200)).length)
    }
}
