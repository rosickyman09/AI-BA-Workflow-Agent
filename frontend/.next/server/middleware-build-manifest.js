self.__BUILD_MANIFEST = {
  "polyfillFiles": [
    "static/chunks/polyfills.js"
  ],
  "devFiles": [
    "static/chunks/react-refresh.js"
  ],
  "ampDevFiles": [],
  "lowPriorityFiles": [],
  "rootMainFiles": [],
  "pages": {
    "/": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/index.js"
    ],
    "/_app": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/_app.js"
    ],
    "/_error": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/_error.js"
    ],
    "/approvals": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/approvals.js"
    ],
    "/documents": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/documents.js"
    ],
    "/generate-urs": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/generate-urs.js"
    ],
    "/knowledge-base": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/knowledge-base.js"
    ],
    "/my-documents": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/my-documents.js"
    ],
    "/projects": [
      "static/chunks/webpack.js",
      "static/chunks/main.js",
      "static/chunks/pages/projects.js"
    ]
  },
  "ampFirstPages": []
};
self.__BUILD_MANIFEST.lowPriorityFiles = [
"/static/" + process.env.__NEXT_BUILD_ID + "/_buildManifest.js",
,"/static/" + process.env.__NEXT_BUILD_ID + "/_ssgManifest.js",

];