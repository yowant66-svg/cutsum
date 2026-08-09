import AppKit
import Foundation

struct CueOverlay: Decodable {
    let sourceText: String
    let translationText: String
    let sourceFontSize: Double
    let translationFontSize: Double
    let maxLines: Int
    let backgroundOpacity: Double
    let maxWidthRatio: Double
    let outputPath: String
}

guard CommandLine.arguments.count == 4 else {
    FileHandle.standardError.write(Data("invalid render arguments\n".utf8))
    exit(2)
}

guard
    let width = Int(CommandLine.arguments[2]),
    let height = Int(CommandLine.arguments[3])
else {
    FileHandle.standardError.write(Data("invalid render dimensions\n".utf8))
    exit(2)
}

do {
    let payload = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
    let cues = try JSONDecoder().decode([CueOverlay].self, from: payload)
    for cue in cues {
        guard let bitmap = NSBitmapImageRep(
            bitmapDataPlanes: nil,
            pixelsWide: width,
            pixelsHigh: height,
            bitsPerSample: 8,
            samplesPerPixel: 4,
            hasAlpha: true,
            isPlanar: false,
            colorSpaceName: .deviceRGB,
            bytesPerRow: 0,
            bitsPerPixel: 0
        ) else {
            throw NSError(domain: "render-cues", code: 3)
        }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
        let horizontalInset = max(
            16,
            CGFloat(width) * CGFloat(1.0 - cue.maxWidthRatio) / 2.0
        )
        let textWidth = CGFloat(width) - (2 * horizontalInset)
        NSColor(calibratedWhite: 0.0, alpha: cue.backgroundOpacity).setFill()
        NSRect(
            x: horizontalInset,
            y: 0,
            width: textWidth,
            height: CGFloat(height)
        ).fill()

        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = .center
        paragraph.lineBreakMode = .byWordWrapping

        func fittingFont(
            text: String,
            preferred: Double,
            availableHeight: CGFloat
        ) -> NSFont {
            var size = min(CGFloat(preferred), max(12, CGFloat(height) * 0.34))
            while size > 10 {
                let font = NSFont.systemFont(ofSize: size, weight: .semibold)
                let bounds = (text as NSString).boundingRect(
                    with: NSSize(
                        width: textWidth,
                        // Measure the complete wrapped text. Constraining this
                        // rect to the drawing height hides overflow and can
                        // falsely accept a font that needs a third line.
                        height: 10_000
                    ),
                    options: [.usesLineFragmentOrigin, .usesFontLeading],
                    attributes: [.font: font, .paragraphStyle: paragraph]
                )
                let maximumHeight = min(
                    availableHeight,
                    font.ascender * CGFloat(max(1, cue.maxLines)) * 1.35
                )
                if bounds.height <= maximumHeight {
                    return font
                }
                size -= 1
            }
            return NSFont.systemFont(ofSize: 10, weight: .semibold)
        }

        let contentHeight = CGFloat(height - 16)
        let hasTranslation = !cue.translationText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        let lineHeight = hasTranslation ? contentHeight / 2 : contentHeight
        let sourceAttributes: [NSAttributedString.Key: Any] = [
            .font: fittingFont(
                text: cue.sourceText,
                preferred: cue.sourceFontSize,
                availableHeight: lineHeight
            ),
            .foregroundColor: NSColor.white,
            .paragraphStyle: paragraph,
        ]
        let translationAttributes: [NSAttributedString.Key: Any] = [
            .font: fittingFont(
                text: cue.translationText,
                preferred: cue.translationFontSize,
                availableHeight: lineHeight
            ),
            .foregroundColor: NSColor(calibratedRed: 1.0, green: 0.92, blue: 0.36, alpha: 1.0),
            .paragraphStyle: paragraph,
        ]
        cue.sourceText.draw(
            in: NSRect(
                x: 16,
                y: hasTranslation ? 8 + lineHeight : 8,
                width: textWidth,
                height: lineHeight
            ).offsetBy(dx: horizontalInset - 16, dy: 0),
            withAttributes: sourceAttributes
        )
        if hasTranslation {
            cue.translationText.draw(
                in: NSRect(
                    x: 16,
                    y: 8,
                    width: textWidth,
                    height: lineHeight
                ).offsetBy(dx: horizontalInset - 16, dy: 0),
                withAttributes: translationAttributes
            )
        }
        NSGraphicsContext.restoreGraphicsState()

        guard
            let png = bitmap.representation(using: .png, properties: [:])
        else {
            throw NSError(domain: "render-cues", code: 4)
        }
        try png.write(
            to: URL(fileURLWithPath: cue.outputPath),
            options: .atomic
        )
    }
} catch {
    FileHandle.standardError.write(Data("could not render subtitle overlays\n".utf8))
    exit(4)
}
