const WebpackRequireFrom = require('webpack-require-from');

module.exports = function override(config, env) {
    config.output.publicPath = 'auto'
    config.output.filename = 'static/schedula/js/[name].[contenthash:8].js'
    config.output.chunkFilename = 'static/schedula/js/[name].[contenthash:8].chunk.js'
    config.output.assetModuleFilename = 'static/schedula/media/[name].[hash][ext]'
    config.plugins[5].options.filename = 'static/schedula/css/[name].[contenthash:8].css'
    config.plugins[5].options.chunkFilename = 'static/schedula/css/[name].[contenthash:8].chunk.css'
    config.resolve.fallback = {fs: false}
    config.devServer = {
        client: {
            overlay: false
        }
    }
    config.module.rules[1].oneOf.splice(2, 0, {
        test: /\.less$/i,
        exclude: /\.module\.(less)$/,
        use: [
            {loader: "style-loader"},
            {loader: "css-loader"},
            {
                loader: "less-loader",
                options: {
                    lessOptions: {
                        strictMath: true,
                        javascriptEnabled: true,
                    },
                },
            },
        ],
    })
    config.plugins.unshift(new WebpackRequireFrom({
        // You can specify a function or a string here
        methodName: 'getPublicPath',  // the name of the function to call at runtime to determine the path
    }))

    return config;
}