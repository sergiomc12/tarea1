// Motor de hashing nativo de FIM (defense_env/fim.py) -- ver CHANGELOG.md
// "candidatos a migracion C/C++ + pybind11". SHA-256 via la API EVP de
// OpenSSL (recomendada en OpenSSL 3.x; las funciones SHA256_* de bajo
// nivel estan deprecadas ahi).
//
// Extension OPCIONAL: fim.py hace try/except al importarla y cae a la
// implementacion Python pura si no esta compilada/disponible (Windows sin
// toolchain de C++, o un servidor sin build-essential/libssl-dev). Nunca
// un requisito duro -- ver Dockerfile (paso de build con "|| true", no
// tumba la imagen entera si el compilado falla).
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <openssl/evp.h>

#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <vector>

namespace py = pybind11;

namespace {

std::string to_hex(const unsigned char *digest, unsigned int len) {
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (unsigned int i = 0; i < len; ++i) {
        oss << std::setw(2) << static_cast<int>(digest[i]);
    }
    return oss.str();
}

struct FileHashResult {
    std::string sha256;
    long long size_bytes;
    double mtime;
};

FileHashResult hash_one_file(const std::string &path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("no se pudo abrir: " + path);
    }

    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    if (ctx == nullptr) {
        throw std::runtime_error("no se pudo inicializar EVP_MD_CTX");
    }
    if (EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr) != 1) {
        EVP_MD_CTX_free(ctx);
        throw std::runtime_error("EVP_DigestInit_ex fallo para: " + path);
    }

    std::vector<char> buffer(65536);
    while (file.read(buffer.data(), static_cast<std::streamsize>(buffer.size())) || file.gcount() > 0) {
        auto read = static_cast<size_t>(file.gcount());
        if (read == 0) {
            break;
        }
        if (EVP_DigestUpdate(ctx, buffer.data(), read) != 1) {
            EVP_MD_CTX_free(ctx);
            throw std::runtime_error("EVP_DigestUpdate fallo para: " + path);
        }
    }

    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_len = 0;
    if (EVP_DigestFinal_ex(ctx, digest, &digest_len) != 1) {
        EVP_MD_CTX_free(ctx);
        throw std::runtime_error("EVP_DigestFinal_ex fallo para: " + path);
    }
    EVP_MD_CTX_free(ctx);

    struct stat st{};
    if (stat(path.c_str(), &st) != 0) {
        throw std::runtime_error("no se pudo stat: " + path);
    }

    FileHashResult result;
    result.sha256 = to_hex(digest, digest_len);
    result.size_bytes = static_cast<long long>(st.st_size);
    result.mtime = static_cast<double>(st.st_mtime);
    return result;
}

}  // namespace

py::dict hash_files(const std::vector<std::string> &paths) {
    py::dict result;
    for (const auto &path : paths) {
        FileHashResult r = hash_one_file(path);
        py::dict entry;
        entry["sha256"] = r.sha256;
        entry["size_bytes"] = r.size_bytes;
        entry["mtime"] = r.mtime;
        result[py::str(path)] = entry;
    }
    return result;
}

PYBIND11_MODULE(_fim_native, m) {
    m.doc() = "Motor de hashing nativo de FIM (defense_env) -- SHA-256 via "
              "OpenSSL EVP, evita el overhead de Path.open()+hashlib+objeto "
              "Pydantic por archivo en el loop caliente de escaneo.";
    m.def("hash_files", &hash_files,
          "Hashea una lista de rutas (str) y devuelve "
          "{path: {sha256, size_bytes, mtime}}. Lanza si un archivo no se "
          "puede abrir o stat-ear.");
}
