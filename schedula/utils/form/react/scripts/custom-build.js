const rewire = require('rewire')
const defaults = rewire('react-scripts/scripts/build.js') // If you ejected, use this instead: const defaults = rewire('./build.js')
let config = defaults.__get__('config')
config.output.publicPath = ''
config.output.filename = 'static/schedula/js/[name].[contenthash:8].js'
config.output.chunkFilename = 'static/schedula/js/[name].[contenthash:8].chunk.js'
config.output.assetModuleFilename = 'static/schedula/media/[name].[hash][ext]'
config.plugins[5].options.filename = 'static/schedula/css/[name].[contenthash:8].css'
config.plugins[5].options.chunkFilename = 'static/schedula/css/[name].[contenthash:8].chunk.css'
config.resolve.fallback = {fs: false}
