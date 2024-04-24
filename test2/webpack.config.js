const glob = require("glob");
const path = require("path");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const TerserWebpackPlugin = require("terser-webpack-plugin");
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");
const webpack = require("webpack")

module.exports = function (_env, argv) {
    const isProduction = argv.mode === "production";
    const isDevelopment = !isProduction;
    const base = path.resolve(__dirname, 'src')
    return {
        devtool: isDevelopment && "cheap-module-source-map",
        mode: argv.mode,
        entry: glob.sync(path.resolve(__dirname, 'src', '**', 'index.js')).reduce((acc, item) => {
            const name = path.dirname(path.relative(base, item));
            acc[name] = item;
            return acc;
        }, {}),
        output: {
            publicPath: 'static/schedula/props/',
            path: path.resolve(__dirname, 'root', 'static', 'schedula', 'props'),
            filename: 'js/[name].js'
        },
        module: {
            rules: [
                {
                    test: /\.(js|jsx)$/,
                    exclude: /node_modules/,
                    use: {
                        loader: "babel-loader",
                        options: {
                            cacheDirectory: true,
                            cacheCompression: false,
                            envName: isProduction ? "production" : "development"
                        }
                    }
                },
                {
                    test: /\.s[ac]ss$/i,
                    use: [
                        // Creates `style` nodes from JS strings
                        isProduction ? MiniCssExtractPlugin.loader : "style-loader",
                        // Translates CSS into CommonJS
                        "css-loader",
                        // Compiles Sass to CSS
                        "sass-loader",
                    ],
                },
                {
                    test: /\.css$/i,
                    use: [
                        // Creates `style` nodes from JS strings
                        isProduction ? MiniCssExtractPlugin.loader : "style-loader",
                        // Translates CSS into CommonJS
                        "css-loader"
                    ],
                },
                {
                    test: /\.(png|jpg|gif)$/i,
                    use: {
                        loader: "url-loader",
                        options: {
                            limit: 8192,
                            name: "media/[name].[hash:8].[ext]"
                        }
                    }
                },
                {
                    test: /\.svg$/,
                    use: ["@svgr/webpack"]
                },
                {
                    test: /\.(eot|otf|ttf|woff|woff2)$/,
                    loader: require.resolve("file-loader"),
                    options: {
                        name: "media/[name].[hash:8].[ext]"
                    }
                }
            ]
        },
        externals: {
            'react': 'React',
            'react-dom': 'ReactDOM'
        },
        plugins: [
            isProduction &&
            new MiniCssExtractPlugin({
                filename: "css/[name].css",
                chunkFilename: "css/[name].[contenthash:8].chunk.css"
            }),
            new webpack.DefinePlugin({
                "process.env.NODE_ENV": JSON.stringify(
                    isProduction ? "production" : "development"
                )
            }),
        ].filter(Boolean),
        optimization: {
            minimize: isProduction,
            minimizer: [
                new TerserWebpackPlugin({
                    terserOptions: {
                        compress: {
                            comparisons: false
                        },
                        mangle: {
                            safari10: true
                        },
                        output: {
                            comments: false,
                            ascii_only: true
                        },
                        warnings: false
                    }
                }),
                new CssMinimizerPlugin()
            ]
        }
    }
}
